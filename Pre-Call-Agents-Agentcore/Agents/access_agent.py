#/Strategy_Agent/Agents/access_agent.py
import json
import boto3
from strands import Agent
from .Tools.execute_redshift_sql import execute_redshift_sql
# from execute_redshift_sql import execute_redshift_sql

# ======================================================
# 0) Redshift Serverless Config (Data API)
# ======================================================
 
WORKGROUP = "sales-copilot-workgroup"
DATABASE = "sales_copilot_db"
SECRET_ARN = (
    "arn:aws:secretsmanager:us-east-1:969385807621:secret:redshift!sales-copilot-namespace-sales_copilot_admin-seNjuJ"
)
 
redshift_client = boto3.client("redshift-data", region_name="us-east-1")


def get_schema_with_samples(table_name: str = "formulary_mart") -> str:
    """
    Fetch schema and sample data dynamically.
    No metadata maintenance required.
    """
    schema_query = f"""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = '{table_name}'
    ORDER BY ordinal_position;
    """
    
    sample_query = f"SELECT * FROM {table_name} LIMIT 3;"
    
    schema_result = execute_redshift_sql(schema_query)
    sample_result = execute_redshift_sql(sample_query)
    
    if schema_result.get("status") != "finished":
        return f"Error fetching schema: {schema_result.get('message')}"
    
    output = [f"Table: {table_name}\n"]
    output.append("Columns:")
    for row in schema_result.get("rows", []):
        output.append(f"  - {row['column_name']}: {row['data_type']}")
    
    output.append("\nSample Data:")
    output.append(json.dumps(sample_result.get("rows", []), indent=2))
    
    return "\n".join(output)

def create_access_agent():
    """
    Access Agent for formulary/access intelligence.
    Role: Provide coverage status updates and actionable opportunities.
    """
    schema_with_samples = get_schema_with_samples("formulary_mart")
    
    return Agent(
        system_prompt=f"""
You are the ACCESS INTELLIGENCE AGENT for pharmaceutical sales.

ROLE: Provide formulary/access intelligence (wins/losses, PA/copay)
INPUTS: Redshift Formulary Marts (formulary_mart table)
OUTPUTS: Coverage status updates, actionable opportunities

{schema_with_samples}

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

OUTPUT FORMAT (JSON only):
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
""",
        tools=[execute_redshift_sql]
    )

access_agent = create_access_agent()

def ask_access_agent(query: str) -> str:
    """Query the access agent"""
    print(f"Access Query: {query}")
    result = access_agent(query)
    return result.text if hasattr(result, "text") else str(result)

if __name__ == "__main__":
    # result = ask_access_agent("Give me access insights for HCP1000")
    # result = ask_access_agent("Show coverage, tier status, PA and copay information for HCP1000 for product PROD-001")
    # result = ask_access_agent("List all insurance plans where prior authorization (PA) was added or removed in the last 30 days")
    result = ask_access_agent("Identify any coverage gaps or non-covered plans for HCP1000 across all products")
    # result = ask_access_agent("Which plans for HCP1000 have high copay or affordability risk for product PROD-001?")
    # result = ask_access_agent("Show plans with severe access friction or high alert severity for HCP1001")
    print(result)