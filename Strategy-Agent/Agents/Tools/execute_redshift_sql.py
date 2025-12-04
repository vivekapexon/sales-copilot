import boto3
from typing import Any, Dict
from strands import tool

# Import gateway client for Lambda invocation via AgentCore Gateway
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from utils.gateway_client import get_gateway_client


def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store. Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3 bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm", region_name="us-east-1")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None


# ----------------------
# Helper: Redshift SQL via AgentCore Gateway Lambda
# ----------------------
@tool
def execute_redshift_sql(sql_query: str, return_results: bool = True) -> Dict[str, Any]:
    """
    Execute arbitrary SQL against Redshift Serverless via AgentCore Gateway Lambda.
    Returns a dict: {"status":"finished","rows":[{col:val,...}, ...]} or error structure.

    - sql_query: SQL string to execute (caller is responsible for safety/validation).
    - return_results: when False, only returns execution status.
    """
    try:
        # Get the gateway client singleton
        client = get_gateway_client()

        # Call the Lambda via AgentCore Gateway
        result = client.call_tool(
            tool_name="execute_redshift_sql",
            arguments={
                "sql_query": sql_query,
                "return_results": return_results
            }
        )

        return result

    except Exception as e:
        return {"status": "error", "message": f"Gateway call error: {str(e)}"}