import os
from strands import Agent, tool
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

MCP_GATEWAY_URL = get_parameter_value("MCP_GATEWAY_URL")
OAUTH_PROVIDER_NAME = get_parameter_value("PROVIDER_NAME")
OAUTH_SCOPE = _parse_scopes(get_parameter_value("SCOPE"))
TABLE_NAME = get_parameter_value("SC_PRC_HCP_ACESS_FORMULARY_TABLE")
TABLE_SCHEMA_DESCRIPTION = get_parameter_value("SC_POC_ACTION_TABLE_SCHEMA")

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


def create_agent():
    """
    Access Agent for formulary/access intelligence.
    Role: Provide coverage status updates and actionable opportunities.
    """
    access_token = asyncio.run(fetch_m2m_token(access_token=""))
    mcp_client = MCPClient(lambda: create_streamable_http_transport(MCP_GATEWAY_URL, access_token))
    mcp_client.__enter__()
    return Agent(
        system_prompt=f"""
          You are the ACCESS INTELLIGENCE AGENT for pharmaceutical sales.

          ROLE: Provide formulary/access intelligence (wins/losses, PA/copay)
          INPUTS: Redshift Formulary Marts {TABLE_NAME}
          OUTPUTS: Coverage status updates, actionable opportunities

          {TABLE_SCHEMA_DESCRIPTION}

          BUSINESS CONTEXT:
          - HCP = Healthcare Provider (physician)
          - Formulary = insurance plan's covered drug list
          - Tier 1-4 (1=preferred/lowest copay, 4=non-preferred/highest copay)
          - Prior Auth (PA) = insurance requires approval before prescribing
          - Step Therapy (ST) = patient must try other drugs first
          - Copay = patient out-of-pocket cost
          - Access barriers = PA, ST, high copay, poor tier placement

          WHAT SALES REPS NEED:
          1. Coverage Status - Where do we stand with this HCP/plan?
          2. Barriers - What's blocking prescriptions?
          3. Changes - What's new that requires action?
          4. Opportunities - Where should I focus my efforts?

          FOCUS ON:
          - Current formulary position, tier placement, access restrictions
          - Prior authorization (PA), step therapy (ST), high copays
          - Formulary wins/losses, policy updates
          - High-impact actions based on payer mix and alert severity
          - Specific actionable insights with numbers and context

          ALWAYS use execute_redshift_sql to query {TABLE_NAME} table.
          NEVER hallucinate data - only use real results from the tool.

          CRITICAL: Return ONLY valid JSON. No explanations, no markdown, no additional text.

          OUTPUT FORMAT:
          {{
            "status": "success",
            "coverage_status": {{
              "tier": <1-4 or null>,
              "prior_auth_requirement": "<None/Some plans/All plans>",
              "step_therapy_requirement": "<None/Some/All>",
              "copay_median_usd": <float or null>,
              "recent_change": "<Win/Loss/None>",
              "alert_severity": "<None/Low/Medium/High>"
            }},
            "actionable_opportunities": [
              "Specific action sales rep can take with context and numbers",
              "Another actionable insight based on payer mix or barriers"
            ],
            "citation": {{
              "source": "{TABLE_NAME}"
            }}
          }}

          If no matching data: {{"status": "error", "message": "No matching data found."}}

          IMPORTANT: Your entire response must be ONLY the JSON object above. Do not add any text before or after the JSON.
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
    payload = payload.get("prompt", "Which plans for HCP1002 have high copay or affordability risk for product PROD-001 on which territory he work on?")
    agent_result = agent(payload)
    return agent_result

# ---------------------------------------------------
# 5) Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()
    #run_main_agent()
