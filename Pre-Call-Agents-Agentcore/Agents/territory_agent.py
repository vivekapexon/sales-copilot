import os
from strands import Agent
import boto3
import asyncio
import re
from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext
from bedrock_agentcore.services.identity import IdentityClient
from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp.mcp_client import MCPClient  
from mcp.client.streamable_http import streamablehttp_client  

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
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
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
)['workloadAccessToken']
 
if workload_access_token:
    BedrockAgentCoreContext.set_workload_access_token(workload_access_token)
else:
    if os.getenv("DOCKER_CONTAINER") == "1":
        raise RuntimeError(
            "WORKLOAD_ACCESS_TOKEN not set. Supply it via: "
            "docker run -e WORKLOAD_ACCESS_TOKEN=<token> ... or inject via secret manager."
        )

@requires_access_token(
    provider_name= OAUTH_PROVIDER_NAME,
    scopes=OAUTH_SCOPE,
    auth_flow="M2M",
)
async def fetch_m2m_token(*, access_token: str):
    return access_token
 
 
def create_streamable_http_transport(mcp_url: str, access_token: str):
    """Helper to create MCP transport with Auth header."""
    return streamablehttp_client(mcp_url, headers={"Authorization": f"Bearer {access_token}"})
 

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
def create_agent():
    """Agent that generates PostgreSQL queries from natural language."""
    access_token = asyncio.run(fetch_m2m_token(access_token=""))
    mcp_client = MCPClient(lambda: create_streamable_http_transport(MCP_GATEWAY_URL, access_token))
    mcp_client.__enter__()
    return Agent(
        system_prompt=f"""
            You are the Territory Agent.
            Your job is to interpret the user’s natural language request about HCP targeting, territory focus, or competitor/access dynamics, then generate a highly precise SQL query to fetch data from Redshift using the registered execute_redshift_sql tool.

            Your responsibilities:
            1. Understand the user’s NLQ even if they don’t give territory, HCP IDs, product name, or disease explicitly.
            2. Identify key intent dimensions:
            - target territory (if missing, infer top territories from data)
            - target behavior (e.g., rising competitor prescriptions, access opportunity)
            - clinical domain (e.g., Diabetes) when provided
            - ranking logic (“call first” → highest priority score)
            3. Generate a SQL query over the healthcare_data table to fetch only the needed fields.
            4. Always filter and sort based on the user's intent using dynamic conditions.
            5. Never hardcode territory_id, product_id, or HCP IDs unless user explicitly mentions them.
            6. Return SQL results ranked with a clear priority score and reason codes.
            7. If the request is about “which territory to focus on”, compute territory-level aggregates.

            Rules:
            - Only use columns that exist in the healthcare_data table.
            - Use conditions matching NLQ intent (competitor rise, access good, high uplift).
            - For “good access”, interpret as:
                formulary_tier_score <= 2 AND
                prior_auth_required_flag = FALSE AND
                step_therapy_required_flag = FALSE
            - For “competitor rise”, interpret using:
                comp_share_28d_delta > 0 OR comp_detail_60d_cnt > 0
            - For unknown territories, group results by territory_id and rank territories.
            - Always produce SQL that can run directly on Redshift.
            - Final output to user must include: ranked list + reason codes + short explanation.

            You must call only the execute_redshift_sql tool to fetch data.
            Never invent data.
            Never return SQL unless calling the tool.

        """,
        tools= get_full_tools_list(mcp_client),
    )


# ---------------------------------------------------
# 3) Main Runner
# ---------------------------------------------------
agent = create_agent()

# ---------------------------------------------------
# 4) Main Workflow
# ------------------------------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}):
    payload = payload.get("prompt", "Today on which territory I need to focus?")
    agent_result = agent(payload)
    return agent_result


# ---------------------------------------------------
# 5) Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()
    #run_main_agent()
