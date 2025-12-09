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

schema_description = """
Columns:
- hcp_id                           VARCHAR(50)      -- e.g., 'HCP1000'
- territory_id                     VARCHAR(50)      -- e.g., 'US-PA-SE'
- access_snapshot_datetime         TIMESTAMP        -- e.g., '2025-10-27 08:24:43'
- recent_formulary_change_30d      VARCHAR(50)      -- NULL or change description
- current_coverage_tier_overall    SMALLINT         -- 1-4 (1=best, 4=worst)
- prior_auth_requirement           VARCHAR(50)      -- 'None', 'Some plans', 'All plans'
- step_therapy_requirement         VARCHAR(50)      -- 'None', 'Some', 'All', 'No'
- copay_status_median_usd          NUMERIC(20,2)    -- Median copay in USD
- patient_mix_top3_summary         VARCHAR(300)     -- e.g., 'BCBS 41%, Medicare 26%, Aetna 11%'
- access_alert_severity            VARCHAR(20)      -- 'None', 'Low', 'Medium', 'High'
- prior_auth_required_flag         BOOLEAN          -- true/false
- step_therapy_required_flag       BOOLEAN          -- true/false
- patient_copay_median_90d         NUMERIC(20,2)    -- 90-day median copay
- access_change_14d_flag           BOOLEAN          -- Recent access change
- access_policy_change_7d_flag     BOOLEAN          -- Recent policy change
- payer_contract_change_30d_flag   BOOLEAN          -- Recent contract change
- formulary_tier_score             SMALLINT         -- Tier score
- payer_top1_share_pct             NUMERIC(10,4)    -- Top payer share %
- payer_top3_share_pct             NUMERIC(10,4)    -- Top 3 payers share %
- access_friction_index            NUMERIC(10,4)    -- Access difficulty score
- physician_id                     VARCHAR(50)      -- e.g., 'HCP-0001'
- product_id                       VARCHAR(50)      -- e.g., 'PROD-001'
- insurance_plan                   VARCHAR(100)     -- e.g., 'Anthem', 'BCBS'
- is_covered                       BOOLEAN          -- true/false
- tier_status                      VARCHAR(50)      -- 'Tier 1', 'Tier 2', 'Not Covered'
- prior_auth_required              BOOLEAN          -- true/false
- step_therapy_required            BOOLEAN          -- true/false
- copay_amount                     NUMERIC(20,2)    -- Copay amount in USD
- last_updated                     TIMESTAMP        -- Last update timestamp
"""

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
          INPUTS: Redshift Formulary Marts (formulary_mart table)
          OUTPUTS: Coverage status updates, actionable opportunities

          {schema_description}

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

          ALWAYS use execute_redshift_sql to query formulary_mart table.
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
              "source": "formulary_mart",
              "primary_key": {{"column": "hcp_id", "value": "<actual_id>"}}
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
