"""
History Agent - LLM-driven SQL over Redshift Serverless
 
- Accepts natural-language history queries
- LLM generates SELECT SQL over history_mart
- Uses Redshift Data API via execute_redshift_sql tool
- Returns ONLY raw JSON from Redshift (no insights)
"""
 
import time
from typing import List, Dict, Any
import json
import boto3
from botocore.exceptions import ClientError
from strands import Agent, tool
from .Tools.execute_redshift_sql import execute_redshift_sql
 
 
# ======================================================
# 0) Redshift Serverless Config (Data API)
# ======================================================
 
WORKGROUP = "sales-copilot-workgroup"
DATABASE = "sales_copilot_db"
SECRET_ARN = (
    "arn:aws:secretsmanager:us-east-1:969385807621:"
    "secret:redshift!sales-copilot-namespace-sales_copilot_admin-seNjuJ"
)
 
redshift_client = boto3.client("redshift-data", region_name="us-east-1")
 
 
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
 
def _tools_list():
    return [execute_redshift_sql]
 
 
def create_history_agent() -> Agent:
    """
    LLM-based History Agent:
    - Interprets natural language history questions
    - Generates a safe SELECT over history_mart
    - Calls execute_redshift_sql
    - Returns ONLY raw JSON (tool output)
    """
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
 
        Query Patterns:
        - For general retrieval: SELECT * FROM history_mart LIMIT 50;
        - For filtering: SELECT * FROM history_mart WHERE <condition>;
        - For sorting: ORDER BY <column> ASC/DESC;
        - For aggregations: SELECT <col>, COUNT(*) FROM history_mart GROUP BY <col>;
        - Multi-condition: Use AND / OR explicitly.
 
    """,
        tools=_tools_list(),
    )
 
 
history_agent = create_history_agent()
 
 
# ======================================================
# 3) Helper for manual testing
# ======================================================
 
def ask_history_agent(query: str) -> str:
    """
    Simple helper function to invoke the History Agent in natural language.
    It returns the agent's text output (which should be JSON from the tool).
    """
    print("NLQ = ", query)
    result = history_agent(query)
    return result.text if hasattr(result, "text") else str(result)
 
 
# Example local test
if __name__ == "__main__":
    ask_history_agent("show recent interactions for types of Digital and Email in last 90 days")
 
 
    # ask_history_agent("show recent interactions for Dr. Smith")
 
    # ask_history_agent("Show all safety objections in last 60 days")
 
    # print(">>> Query: Show recent interactions for Dr. Smith")
    # print(ask_history_agent("Show recent interactions for Dr. Smith"))
    # print("\n----------------------------------\n")
 
    # print(">>> Query: Show all safety objections in last 60 days")
    # print(ask_history_agent("Show all safety objections in last 60 days"))
    # print("\n----------------------------------\n")