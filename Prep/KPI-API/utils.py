# utils.py
import boto3
import time
import logging
from typing import Dict, Any

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("KPI_utils_agent")

AWS_REGION = "us-east-1"

# -------------------------------------------------
# Global AWS clients (CRITICAL for Lambda reuse)
# -------------------------------------------------
redshift_client = boto3.client("redshift-data", region_name=AWS_REGION)
ssm_client = boto3.client("ssm", region_name=AWS_REGION)

# -------------------------------------------------
# Redshift Config
# -------------------------------------------------
WORKGROUP = "sales-copilot-workgroup"
DATABASE = "sales_copilot_db"
SECRET_ARN = (
    "arn:aws:secretsmanager:us-east-1:969385807621:"
    "secret:redshift!sales-copilot-namespace-sales_copilot_admin-seNjuJ"
)

SQL_POLL_INTERVAL_SECONDS = 1.0
SQL_POLL_MAX_SECONDS = 300.0

# -------------------------------------------------
# Warm-up on cold start (runs ONCE per container)
# -------------------------------------------------
try:
    redshift_client.execute_statement(
        WorkgroupName=WORKGROUP,
        Database=DATABASE,
        SecretArn=SECRET_ARN,
        Sql="SELECT 1"
    )
    logger.info("Redshift warm-up executed")
except Exception as e:
    logger.warning("Redshift warm-up skipped: %s", e)

# -------------------------------------------------
# SSM helper
# -------------------------------------------------
def get_parameter_value(parameter_name):
    try:
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=True
        )
        return response["Parameter"]["Value"]
    except Exception as e:
        logger.error("SSM error: %s", e)
        return None

# -------------------------------------------------
# Redshift SQL Executor with Timing
# -------------------------------------------------
def execute_redshift_sql(sql_query: str, return_results: bool = True) -> Dict[str, Any]:
    timings = {}
    start_total = time.time()

    try:
        t0 = time.time()
        resp = redshift_client.execute_statement(
            WorkgroupName=WORKGROUP,
            Database=DATABASE,
            SecretArn=SECRET_ARN,
            Sql=sql_query
        )
        stmt_id = resp["Id"]
        timings["execute_statement_sec"] = round(time.time() - t0, 3)

        # Polling
        t1 = time.time()
        elapsed = 0.0
        while elapsed < SQL_POLL_MAX_SECONDS:
            desc = redshift_client.describe_statement(Id=stmt_id)
            status = desc.get("Status")
            if status in ("FINISHED", "FAILED", "ABORTED"):
                break
            time.sleep(SQL_POLL_INTERVAL_SECONDS)
            elapsed += SQL_POLL_INTERVAL_SECONDS

        timings["polling_sec"] = round(time.time() - t1, 3)

        if status != "FINISHED":
            return {
                "status": status,
                "message": desc.get("Error"),
                "statement_id": stmt_id,
                "timings": timings
            }

        if not return_results:
            return {"status": "finished", "statement_id": stmt_id}

        # Fetch results
        t2 = time.time()
        results = redshift_client.get_statement_result(Id=stmt_id)
        timings["fetch_results_sec"] = round(time.time() - t2, 3)

        columns = [c["name"] for c in results["ColumnMetadata"]]
        rows = []

        for record in results["Records"]:
            row = {}
            for i, cell in enumerate(record):
                row[columns[i]] = next(iter(cell.values())) if cell else None
            rows.append(row)

        timings["total_sec"] = round(time.time() - start_total, 3)

        logger.info("Redshift timings: %s", timings)

        return {
            "status": "finished",
            "rows": rows,
            "statement_id": stmt_id,
            "timings": timings
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
