#utils.py
#Function to query sql queries in redshift.
#Access parameter store to get revelents parameter value from AWS SSM
#
import boto3
from typing import Dict, Any
import time
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name= "us-east-1")
import logging
from bedrock_agentcore.runtime import BedrockAgentCoreApp
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("KPI_utils_agent")
s3_client = boto3.client("s3")
app = BedrockAgentCoreApp()

def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store. Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3 bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm",region_name="us-east-1")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None

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
SQL_POLL_INTERVAL_SECONDS = 1.0
SQL_POLL_MAX_SECONDS = 300.0

# ----------------------
# Helper: Redshift Data API tool
# ----------------------

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
