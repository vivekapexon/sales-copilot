import json
from strands import Agent, tool
from .Tools.execute_redshift_sql import execute_redshift_sql
import boto3

def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store. Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3 bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None

HCP_SCHEMA_COLUMNS = get_parameter_value("SC_HCP_SCHEMA_COLUMNS")

# ---------------------------------------------------
# 2) Agent Definition
# ---------------------------------------------------

def _tools_list():
    return [execute_redshift_sql]


def create_profile_agent():
    """Agent that generates PostgreSQL queries from natural language."""
    return Agent(
        system_prompt=f"""
            You are the ProfileAgent.
            Your task is to generate PostgreSQL SELECT queries from natural-language user prompts.

            Rules:
            1. The table name is `healthcare_data`.
            2. You must only use these allowed columns:
            {", ".join(HCP_SCHEMA_COLUMNS)}
            3. Always produce a valid PostgreSQL SQL query.
            4. Never guess values not mentioned. If value is unclear, use placeholders:
                {{value}}
            5. Just select specific columns needed to answer the prompt, do NOT use SELECT *.
            6. stored this SQL query in the variable `sql_query`.
            7. Pass created SQL query to the tool `execute_redshift_sql(sql_query)` for execution.
            8. If user asks for something impossible with the schema, return:
            {{
                "sql_query": "UNSUPPORTED_QUERY"
            }}

            Strict Output Rules:
            - Always return the final answer as a simple JSON object as per user request.
            - No need to print all columns just display the columns which shows the details asked in the prompt.
            - If multiple rows, return as list of dicts.
            - If single metric, return as key-value pair.
            - Add simple two liner explanations if needed.
            - No other columns except those requested,No SQL, no logs.

            Query Patterns:
            - For general retrieval: SELECT * FROM healthcare_data LIMIT 50;
            - For filtering: SELECT * FROM healthcare_data WHERE <condition>;
            - For sorting: ORDER BY <column> ASC/DESC;
            - For aggregations: SELECT <col>, COUNT(*) FROM healthcare_data GROUP BY <col>;
            - Multi-condition: Use AND / OR explicitly.
            
            You must always generate the most reasonable SQL based on the user's text.
        """,
        tools=_tools_list(),
    )


# ---------------------------------------------------
# 3) Main Runner
# ---------------------------------------------------

def run_main_agent(prompt: str):
    agent = create_profile_agent()
    result = agent(prompt)
    print("Generated SQL:", result)
    return result


# ---------------------------------------------------
# 4) Local Execution
# ---------------------------------------------------
if __name__ == "__main__":
    prompt = input("Enter your prompt: ")
    run_main_agent(prompt)