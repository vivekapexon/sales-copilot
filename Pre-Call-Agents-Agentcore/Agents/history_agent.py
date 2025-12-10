"""
History Agent - LLM-driven SQL over Redshift Serverless

- Accepts natural-language history queries
- LLM generates SELECT SQL over history_mart
- Uses Redshift Data API via execute_redshift_sql tool
- Returns ONLY raw JSON from Redshift (no insights)
"""
import re
import os
import asyncio
import boto3

from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext
from bedrock_agentcore.services.identity import IdentityClient
from bedrock_agentcore.identity.auth import requires_access_token
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

app = BedrockAgentCoreApp()

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


# ======================================================
schema_description = """
Table: history_mart
 
Columns:
- hcp_id                       VARCHAR      -- e.g., 'HCP1000'
- hcp_name                     VARCHAR      -- e.g., 'Dr. Smith'
- territory_id                 VARCHAR      -- e.g., 'US-PA-E'
- call_date                    DATE         -- e.g., '2025-09-30'
- interaction_type             VARCHAR      -- Email | Phone Call | Physical | Webinar | Digital
- topic_discussed              VARCHAR      -- 'Responder rates', 'Safety overview', 'MOA discussion', etc.
- objection_raised             VARCHAR      -- 'None', 'Cost', 'Safety', 'Access', 'Efficacy'
- materials_shared             VARCHAR      -- 'Payer sheet', 'KOL video', 'Safety FAQ', 'MOA email', 'None'
- outcome                      VARCHAR      -- 'Requested follow-up deck', 'Declined', 'Rescheduled', 'Positive next step', 'Neutral'
- followup_flag                VARCHAR      -- 'Yes' or 'No'
- opened_moa_email_flag        VARCHAR      -- 'Yes' or 'No'
- clicked_kol_video_flag       VARCHAR      -- 'Yes' or 'No'
- clicked_campaign_link_flag   VARCHAR      -- 'Yes' or 'No'
- formulary_update_30d_flag    VARCHAR      -- 'Yes' or 'No'
- formulary_update_summary     VARCHAR      -- e.g., 'Tier updated; PA required.' or 'Tier updated; PA removed.'
"""
# ======================================================


# ======================================================
# 2) History Agent (LLM generates SQL → calls execute_redshift_sql)
# ======================================================

# def _tools_list():
#     return [execute_redshift_sql]


def create_history_agent() -> Agent:
    """
    LLM-based History Agent:
    - Interprets natural language history questions
    - Generates a safe SELECT over history_mart
    - Calls execute_redshift_sql
    - Returns ONLY raw JSON (tool output)
    """
    access_token = asyncio.run(fetch_m2m_token(access_token=""))
    mcp_client = MCPClient(
        lambda: create_streamable_http_transport(MCP_GATEWAY_URL, access_token)
    )
    mcp_client.__enter__()
    return Agent(
        system_prompt=f"""
        You are the **History Agent** in a multi-agent Sales Copilot system.
 
        Your job:
        - Convert natural-language history questions into SQL over the `history_mart` table.
        - ALWAYS call the `execute_redshift_sql` tool with the SQL you generate.
 
        Rules:
            1. The table name is `history_mart`.
            2. You must only use these allowed columns:
            {", ".join(schema_description)}
            3. Always produce a valid Redshift SQL query.
            4. Never guess values not mentioned. If value is unclear, use placeholders:
                {{value}}
            5. stored this SQL query in the variable `sql_query`.
            6. Pass created SQL query to the tool `execute_redshift_sql(sql_query)` for execution.
            7. If user asks for something impossible with the schema, return:
            {{
                "sql_query": "UNSUPPORTED_QUERY"
            }}
 
        Strict Output Format:
        - Base on user query, only include relevant fields in the output JSON.
        Example: If user asks for interaction types and call dates,
        return: {{
                    "interaction_type": "Phone Call",
                    "call_date": "2025-08-12"
                }}
        - Do NOT add any extra columns details,  commentary or explanation.
        - Include the data source table name also from where the data fetched
 
        Query Patterns:
        - For general retrieval: SELECT * FROM history_mart LIMIT 50;
        - For filtering: SELECT * FROM history_mart WHERE <condition>;
        - For sorting: ORDER BY <column> ASC/DESC;
        - For aggregations: SELECT <col>, COUNT(*) FROM history_mart GROUP BY <col>;
        - Multi-condition: Use AND / OR explicitly.
 
    """,
        tools=get_full_tools_list(mcp_client),
    )


history_agent = create_history_agent()


# ======================================================
# 3) Helper for manual testing
# ======================================================
@app.entrypoint
def ask_history_agent(payload: dict = {}) -> str:
    """
    Simple helper function to invoke the History Agent in natural language.
    It returns the agent's text output (which should be JSON from the tool).
    """
    payload = payload.get(
        "prompt",
        "show recent interactions for Dr. Smith",
    )
    result = history_agent(payload)
    return result.text if hasattr(result, "text") else str(result)


# Example local test
if __name__ == "__main__":
    app.run()

    # ask_history_agent("show recent interactions for Dr. Smith")

    # ask_history_agent("Show all safety objections in last 60 days")

    # print(">>> Query: Show recent interactions for Dr. Smith")
    # print(ask_history_agent("Show recent interactions for Dr. Smith"))
    # print("\n----------------------------------\n")

    # print(">>> Query: Show all safety objections in last 60 days")
    # print(ask_history_agent("Show all safety objections in last 60 days"))
    # print("\n----------------------------------\n")
