import json
import time
import boto3

def get_parameter_value(parameter_name):
    """
    Fetch a parameter from AWS Systems Manager Parameter Store.
    
    Args:
        parameter_name (str): The name of the parameter to retrieve from Parameter Store.
    
    Returns:
        str: The parameter value if successful, None otherwise.
    """
    try:
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None

# ----------------------
# Configuration 
# ----------------------
# Redshift workgroup name retrieved from Parameter Store
WORKGROUP = get_parameter_value("REDSHIFT_WORKGROUP")
# Redshift database name retrieved from Parameter Store
DATABASE = get_parameter_value("SC_REDSHIFT_DATABASE")
# Redshift secret ARN for authentication retrieved from Parameter Store
SECRET_ARN = get_parameter_value("SC_REDSHIFT_SECRET_ARN")

# Default maximum number of rows to return from SQL queries
DEFAULT_SQL_LIMIT = 1000
# Interval (in seconds) between polling for query execution status
SQL_POLL_INTERVAL_SECONDS = 0.5
# Maximum time (in seconds) to wait for query execution to complete
SQL_POLL_MAX_SECONDS = 30.0


def lambda_handler(event, context):
    """
    Lambda handler function to execute Redshift SQL queries.
    
    Expected event payload:
    {
        "sql_query": "SELECT 1",
        "return_results": true
    }
    
    Args:
        event (dict): Lambda event containing 'sql_query' and optional 'return_results' flag.
        context (object): Lambda context object.
    
    Returns:
        dict: Response object with statusCode and JSON body containing execution results or errors.
    """
    # Extract SQL query from event payload
    sql_query = event.get("sql_query")
    # Determine whether to return query results (default: True)
    return_results = event.get("return_results", True)

    # Validate that SQL query is provided
    if not sql_query:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing 'sql_query' in request"})
        }

    # Initialize Redshift Data API client
    client = boto3.client("redshift-data")

    # Execute the SQL statement and retrieve statement ID
    try:
        resp = client.execute_statement(
            WorkgroupName=WORKGROUP,
            Database=DATABASE,
            SecretArn=SECRET_ARN,
            Sql=sql_query
        )
        stmt_id = resp["Id"]
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": f"execute_statement error: {str(e)}"
            })
        }

    # Poll for query execution status until completion or timeout
    elapsed = 0.0
    status = None

    while elapsed < SQL_POLL_MAX_SECONDS:
        try:
            # Get current statement execution status
            status_resp = client.describe_statement(Id=stmt_id)
            status = status_resp.get("Status")
        except Exception as e:
            return {
                "statusCode": 500,
                "body": json.dumps({
                    "status": "error",
                    "message": f"describe_statement error: {str(e)}"
                })
            }

        # Break polling loop if statement has reached terminal state
        if status in ("FINISHED", "ABORTED", "FAILED"):
            break

        # Wait before next poll attempt
        time.sleep(SQL_POLL_INTERVAL_SECONDS)
        elapsed += SQL_POLL_INTERVAL_SECONDS

    # Handle non-finished query execution status
    if status != "FINISHED":
        try:
            status_resp = client.describe_statement(Id=stmt_id)
            err = status_resp.get("Error")
        except Exception:
            err = "Statement did not finish within time limit."

        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": status,
                "message": err
            })
        }

    # Return early if results are not requested
    if not return_results:
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "finished",
                "statement_id": stmt_id
            })
        }

    # Retrieve query results from Redshift
    try:
        results = client.get_statement_result(Id=stmt_id)
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({
                "status": "error",
                "message": f"get_statement_result error: {str(e)}"
            })
        }

    # Extract column names from result metadata
    column_info = [c["name"] for c in results.get("ColumnMetadata", [])]
    records = []

    # Parse each row and convert cell values to appropriate Python types
    for row in results.get("Records", []):
        parsed_row = {}
        for idx, cell in enumerate(row):
            # Get column name or use default naming
            col_name = column_info[idx] if idx < len(column_info) else f"col_{idx}"
            
            # Extract value based on cell type
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
                # Fallback: extract first value from cell
                parsed_row[col_name] = list(cell.values())[0] if cell else None

        records.append(parsed_row)

    # Return successful execution response with results
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": "finished",
            "rows": records,
            "statement_id": stmt_id
        })
    }