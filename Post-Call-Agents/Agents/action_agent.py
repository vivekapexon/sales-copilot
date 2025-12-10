# /post_call/Agents/action_agent.py
import json
import boto3
import os
from dotenv import load_dotenv
from strands import Agent, tool
from .Tools.execute_redshift_sql import execute_redshift_sql

# ---------------------------------------------------
# 0) JSON
# ---------------------------------------------------


# ---------------------------------------------------
# 2) Agent Definition
# ---------------------------------------------------

def _tools_list():
    return [execute_redshift_sql]


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
    return Agent(
        system_prompt="""
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
            - If call_id is provided:
                SELECT * FROM call_action_items
                WHERE call_id = '<CALL_ID>'
                ORDER BY priority_score DESC
                LIMIT 1;

            - If no call_id is provided:
                SELECT * FROM call_action_items
                ORDER BY priority_score DESC
                LIMIT 1;

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

            {
            "call_id": "",
            "hcp_id": "",
            "tasks": [
                {
                    "task_type": "",
                    "owner": "",
                    "due_date": "",
                    "priority": 0,
                    "status": "READY_FOR_CREATION",
                    "metadata": {}
                }
            ],
            "sample_request": {
                "required": true/false,
                "qty": 0
            },
            "hub_referral": {
                "required": true/false
            },
            "calendar_event": {
                "required": true/false,
                "minutes": 0
            },
            "crm_update": {
                "ready": true/false,
                "payload": {}
            }
            }

            Rules:
            - Do NOT include SQL or logs in the final JSON.
            - Do NOT hallucinate values.
            - If something is missing, leave it empty but do not guess.
            - If no record found, respond:
            { "error": "No action records found." }

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
                        {
                        "task_type": action_type,
                        "owner": owner,
                        "due_date": <due_date>,
                        "priority": priority_score,
                        "status": "READY_FOR_CREATION",
                        "metadata": {}
                        }

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
        tools=_tools_list(),
    )

agent = create_agent()


# ---------------------------------------------------
# 3) Main Runner
# ---------------------------------------------------

def run_main_agent(nlq: str):
    instruction = nlq
    result = agent(instruction)
    return result


# ---------------------------------------------------
# 4) Local Run
# ---------------------------------------------------
if __name__ == "__main__":
    #"Run the ActionAgent for call_id CALL-2025-0001.
    prompt = input("Enter your prompt: ")
    run_main_agent(prompt)
