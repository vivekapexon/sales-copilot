import re
import os
import asyncio
import boto3
from strands import Agent
from bedrock_agentcore.runtime import (
    BedrockAgentCoreApp, BedrockAgentCoreContext
    )
from bedrock_agentcore.services.identity import IdentityClient
from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client


app = BedrockAgentCoreApp()


# ---------------------------------------------------
# 0) HCP Table Schema
# ---------------------------------------------------
def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager
      Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or
        None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store.
         Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3
            bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm", region_name="us-east-1")
        response = ssm_client.get_parameter(
            Name=parameter_name, WithDecryption=True
            )
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None


def _parse_scopes(s: str) -> list[str]:
    if not s:
        return []
    parts = re.split(r"[,\s]+", s.strip())
    return [p for p in parts if p]


HCP_SCHEMA_COLUMNS = get_parameter_value("SC_HCP_SCHEMA_COLUMNS")
MCP_GATEWAY_URL = get_parameter_value("MCP_GATEWAY_URL")
OAUTH_PROVIDER_NAME = get_parameter_value("PROVIDER_NAME")
OAUTH_SCOPE = _parse_scopes(get_parameter_value("SCOPE"))


# ---------------------------------------------------
# 1) Identity & Access Bootstrap
# ---------------------------------------------------
identity_client = IdentityClient("us-east-1")
workload_access_token = identity_client.get_workload_access_token(
    workload_name="Sales-Copilet-Agents",
)["workloadAccessToken"]

if workload_access_token:
    BedrockAgentCoreContext.set_workload_access_token(workload_access_token)
else:
    if os.getenv("DOCKER_CONTAINER") == "1":
        raise RuntimeError(
            "WORKLOAD_ACCESS_TOKEN not set. Supply it via: "
            "docker run -e WORKLOAD_ACCESS_TOKEN=<token> ... or inject via secret manager."
        )


@requires_access_token(
    provider_name=OAUTH_PROVIDER_NAME,
    scopes=OAUTH_SCOPE,
    auth_flow="M2M",
)
async def fetch_m2m_token(*, access_token: str):
    return access_token


def create_streamable_http_transport(mcp_url: str, access_token: str):
    """Helper to create MCP transport with Auth header."""
    return streamablehttp_client(
        mcp_url, headers={"Authorization": f"Bearer {access_token}"}
    )


def get_full_tools_list(client):
    """List all tools from MCP Gateway (supports pagination)."""
    tools = []
    pagination_token = None
    while True:
        result = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(result)
        if not result.pagination_token:
            break
        pagination_token = result.pagination_token
    return tools


# ---------------------------------------------------
# 2) Agent Definition
# ---------------------------------------------------

# def _tools_list():
#     return [execute_redshift_sql]


def create_profile_agent():
    """Agent that generates PostgreSQL queries from natural language."""
    access_token = asyncio.run(fetch_m2m_token(access_token=""))
    mcp_client = MCPClient(
        lambda: create_streamable_http_transport(MCP_GATEWAY_URL, access_token)
    )
    mcp_client.__enter__()
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
            - Include the data source table name also from where the data fetched
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
        tools=get_full_tools_list(mcp_client),
    )


# ---------------------------------------------------
# 3) Main Runner
# ---------------------------------------------------
agent = create_profile_agent()


# ---------------------------------------------------
# 4) Main Workflow
# ------------------------------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}):
    payload = payload.get("prompt", "Give me the details of HCP1001")
    agent_result = agent(payload)
    return agent_result


# ---------------------------------------------------
# 5) Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    #app.run()
    run_main_agent()
