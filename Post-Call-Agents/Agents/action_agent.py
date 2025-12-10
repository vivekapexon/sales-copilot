# /post_call/Agents/action_agent.py
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

# ---------------------------------------------------
# 0) JSON
# ---------------------------------------------------
ACTION_SCHEMA_COLUMNS = {
  "table_name": "public.call_action_items",
  "description": "Stores extracted post-call action items for each HCP and Call interaction. Used by the Action Agent to generate tasks, sample requests, hub referrals, calendar blocks, and CRM payloads.",

  "columns": {
    "hcp_id": {
      "type": "varchar(50)",
      "description": "Unique identifier for the HCP associated with the call."
    },
    "call_id": {
      "type": "varchar(100)",
      "description": "Unique call identifier. Primary lookup key for the Action Agent."
    },
    "action_items_json": {
      "type": "varchar(65535)",
      "description": "JSON array of action items extracted from the post-call conversation. Each item contains action_type, owner, due_date."
    },
    "primary_action_type": {
      "type": "varchar(100)",
      "description": "Primary or dominant action type for the call."
    },
    "task_due_date": {
      "type": "date",
      "description": "Default due date for the primary task."
    },
    "task_owner_role": {
      "type": "varchar(100)",
      "description": "Role responsible for executing the primary task, e.g., Rep, Access Specialist, MedInfo."
    },
    "sample_request_qty": {
      "type": "integer",
      "description": "Number of samples requested by HCP. 0 if none."
    },
    "hub_referral_flag": {
      "type": "varchar(10)",
      "description": "Indicates if a HUB referral is required. Values: 'Yes' or 'No'."
    },
    "calendar_block_minutes": {
      "type": "integer",
      "description": "Amount of time (in minutes) to block in the rep's calendar."
    },
    "priority_score": {
      "type": "integer",
      "description": "Score representing priority level of the call and tasks. Higher means higher priority."
    }
  },

  "primary_keys": ["call_id", "hcp_id"],

  "query_patterns": {
    "lookup_by_call_id": {
      "description": "Fetch single call action entry using call_id.",
      "sql": "SELECT * FROM public.call_action_items WHERE call_id = '<CALL_ID>' ORDER BY priority_score DESC LIMIT 1;"
    },
    "lookup_by_hcp_id": {
      "description": "Fetch latest action entry for a given HCP.",
      "sql": "SELECT * FROM public.call_action_items WHERE hcp_id = '<HCP_ID>' ORDER BY priority_score DESC LIMIT 1;"
    },
    "lookup_next_high_priority": {
      "description": "Fetch next highest priority pending action if no call_id provided.",
      "sql": "SELECT * FROM public.call_action_items ORDER BY priority_score DESC LIMIT 1;"
    },
    "fetch_all_actions_for_call": {
      "description": "Fetch all actions tied to a specific call.",
      "sql": "SELECT * FROM public.call_action_items WHERE call_id = '<CALL_ID>' ORDER BY priority_score DESC;"
    }
  },

  "action_item_json_format": {
    "description": "Expected structure inside action_items_json column.",
    "example": [
      {
        "action_type": "submit_PA_support",
        "due_date": "2025-10-22",
        "owner": "Access Specialist"
      },
      {
        "action_type": "log_samples",
        "due_date": "2025-10-23",
        "owner": "Rep"
      },
      {
        "action_type": "initiate_MI_response",
        "due_date": "2025-10-24",
        "owner": "MedInfo"
      }
    ]
  },

  "business_rules": {
    "sample_request_rule": "sample_request_qty > 0 indicates a sample task must be created.",
    "hub_referral_rule": "hub_referral_flag == 'Yes' indicates a HUB referral task.",
    "calendar_block_rule": "calendar_block_minutes > 0 requires a calendar event to be created.",
    "priority_rule": "priority_score is used to determine urgency and ordering of tasks.",
    "owner_assignment_rule": "task_owner_role overrides individual action owner if missing."
  }
}


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
            1. The table name is `call_action_items`.
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