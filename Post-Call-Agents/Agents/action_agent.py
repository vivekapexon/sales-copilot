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
TABLE_NAME = get_parameter_value("SC_POC_ACTION_TABLE")
ACTION_SCHEMA_COLUMNS = get_parameter_value("SC_POC_ACTION_TABLE_SCHEMA")

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
    """
    ActionAgent:
    Turns action_items_json into:
      - tasks
      - hub referral object
      - sample requests
      - crm update payload
      - calendar event payload
    """
    access_token = asyncio.run(fetch_m2m_token(access_token=""))
    mcp_client = MCPClient(lambda: create_streamable_http_transport(MCP_GATEWAY_URL, access_token))
    mcp_client.__enter__()
    return Agent(
        system_prompt=f"""
            You are the ActionAgent.

            Your job is to convert post-call extracted action items into structured task payloads.
            You do NOT write to DynamoDB or CRM. You only produce the final JSON task bundle.

            You have only one tool: `execute_redshift_query`.
            Use it to fetch the action extraction row from Redshift.

            ------------------------------------------------------------
            1. HOW INPUTS WORK
            ------------------------------------------------------------

            In the user instruction you may receive:
            - A specific `call_id` (preferred)
            - A specific `hcp_id` (optional)
            - A structured note JSON (optional)
            - A compliance result JSON (optional)

            Your first step:
            ---------------------------------------------
            1. The table name is {TABLE_NAME}.
            2. You must only use these allowed columns:
            {", ".join(ACTION_SCHEMA_COLUMNS)}
            3. Always produce a valid PostgreSQL SQL query.
            4. Never guess values not mentioned. If value is unclear, use placeholders:
                {{value}}
            5. Just select specific columns needed to answer the prompt, do NOT use SELECT *.
            6. stored this SQL query in the variable `sql_query`.
            7. Pass created SQL query to the tool `execute_redshift_sql(sql_query)` for execution.

            - Pass query to execte_redshift_sql tool
        
            ------------------------------------------------------------
            2. WHAT YOU MUST DO
            ------------------------------------------------------------

            You must:
            - Parse the action_items_json
            - Normalize due_dates, owners, priorities
            - Identify sample tasks
            - Identify PA support tasks
            - Identify MI response tasks
            - Identify hub referral tasks
            - Identify CRM update requirements
            - Identify calendar event requirements

            ------------------------------------------------------------
            3. OUTPUT FORMAT (STRICT)
            ------------------------------------------------------------

            Your final output must be ONLY the following JSON:

            {{
            "call_id": "",
            "hcp_id": "",
            "tasks": [
                {{
                    "task_type": "",
                    "owner": "",
                    "due_date": "",
                    "priority": 0,
                    "status": "READY_FOR_CREATION",
                    "metadata": {{}}
                }}
            ],
            "sample_request": {{
                "required": true/false,
                "qty": 0
            }},
            "hub_referral": {{
                "required": true/false
            }},
            "calendar_event": {{
                "required": true/false,
                "minutes": 0
            }},
            "crm_update": {{
                "ready": true/false,
                "payload": {{}}
            }}
            }}

            Rules:
            - Do NOT include SQL or logs in the final JSON.
            - Do NOT hallucinate values.
            - If something is missing, leave it empty but do not guess.
            - If no record found, respond:
            {{ "error": "No action records found." }}

            ------------------------------------------------------------
            4. WORKFLOW
            ------------------------------------------------------------

            1. Parse the user instruction:
            - detect call_id if present
            - detect optional structured note JSON
            - detect optional compliance JSON (if provided)

            2. Build SQL query string exactly as above.

            3. Call:
            result = execute_redshift_query(sql, True)

            4. If result is empty:
            return error JSON.

            5. Otherwise:
            - Extract row
            - Parse action_items_json (list)
            - For each:
                - Normalize: type, owner, due date, priority
                - Build a task entry:
                        {{
                        "task_type": action_type,
                        "owner": owner,
                        "due_date": <due_date>,
                        "priority": priority_score,
                        "status": "READY_FOR_CREATION",
                        "metadata": {{}}
                        }}

            6. Sample request:
            - required if sample_request_qty > 0

            7. Hub referral:
            - required if hub_referral_flag == "Yes" or True

            8. Calendar:
            - required if calendar_block_minutes > 0

            9. CRM update:
            - always ready if tasks exist

            Return ONLY the JSON defined above.
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
    payload = payload.get("prompt", "Give me action items for hcp_id 'HCP1001'")
    agent_result = agent(payload)
    return agent_result


# ---------------------------------------------------
# 5) Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()
    #run_main_agent()