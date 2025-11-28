import time
import boto3
from typing import Any, Dict
from strands import tool

# ----------------------
# Configuration 
# ----------------------
WORKGROUP = "sales-copilot-workgroup"
DATABASE = "sales_copilot_db"
SECRET_ARN = (
    "arn:aws:secretsmanager:us-east-1:969385807621:"
    "secret:redshift!sales-copilot-namespace-sales_copilot_admin-seNjuJ"
)

# Optional: set a default row limit for arbitrary SQL to avoid accidental full-table scans
DEFAULT_SQL_LIMIT = 1000
SQL_POLL_INTERVAL_SECONDS = 0.5
SQL_POLL_MAX_SECONDS = 30.0

# ----------------------
# Helper: Redshift Data API tool
# ----------------------
@tool
def execute_redshift_sql(sql_query: str, return_results: bool = True) -> Dict[str, Any]:
    """
    Execute arbitrary SQL against Redshift Serverless Data API (workgroup mode).
    Returns a dict: {"status":"finished","rows":[{col:val,...}, ...]} or error structure.

    - sql_query: SQL string to execute (caller is responsible for safety/validation).
    - return_results: when False, only returns execution status.
    """
    client = boto3.client("redshift-data")
    try:
        resp = client.execute_statement(
            WorkgroupName=WORKGROUP,
            Database=DATABASE,
            SecretArn=SECRET_ARN,
            Sql=sql_query
        )
        stmt_id = resp["Id"]
    except Exception as e:
        return {"status": "error", "message": f"execute_statement error: {str(e)}"}

    # Poll for completion
    elapsed = 0.0
    while elapsed < SQL_POLL_MAX_SECONDS:
        try:
            status_resp = client.describe_statement(Id=stmt_id)
            status = status_resp.get("Status")
        except Exception as e:
            return {"status": "error", "message": f"describe_statement error: {str(e)}"}
        if status in ("FINISHED", "ABORTED", "FAILED"):
            break
        time.sleep(SQL_POLL_INTERVAL_SECONDS)
        elapsed += SQL_POLL_INTERVAL_SECONDS

    if status != "FINISHED":
        # Try to return error details if available
        try:
            status_resp = client.describe_statement(Id=stmt_id)
            return {"status": status, "message": status_resp.get("Error")}
        except Exception:
            return {"status": status, "message": "Statement did not finish within time limit."}

    if not return_results:
        return {"status": "finished", "statement_id": stmt_id}

    # Retrieve results
    try:
        results = client.get_statement_result(Id=stmt_id)
    except Exception as e:
        return {"status": "error", "message": f"get_statement_result error: {str(e)}"}

    column_info = [c["name"] for c in results.get("ColumnMetadata", [])]
    records = []
    for row in results.get("Records", []):
        # Each row: list of field dicts, convert to native types where possible
        parsed_row = {}
        for idx, cell in enumerate(row):
            col_name = column_info[idx] if idx < len(column_info) else f"col_{idx}"
            # cell is like {"stringValue": "..."} or {"longValue": 123} etc.
            if "stringValue" in cell:
                parsed_row[col_name] = cell["stringValue"]
            elif "blobValue" in cell:
                parsed_row[col_name] = cell["blobValue"]
            elif "doubleValue" in cell:
                parsed_row[col_name] = cell["doubleValue"]
            elif "longValue" in cell:
                parsed_row[col_name] = cell["longValue"]
            elif "booleanValue" in cell:
                parsed_row[col_name] = cell["booleanValue"]
            elif "isNull" in cell and cell["isNull"]:
                parsed_row[col_name] = None
            else:
                # unknown form; store raw
                parsed_row[col_name] = list(cell.values())[0] if cell else None
        records.append(parsed_row)

    return {"status": "finished", "rows": records, "statement_id": stmt_id}