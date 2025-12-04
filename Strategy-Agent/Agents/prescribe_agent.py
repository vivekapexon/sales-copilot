import json
from strands import Agent
from .Tools.execute_redshift_sql import execute_redshift_sql
import boto3

# ----------------------
# Configuration 
# ----------------------
DEFAULT_SQL_LIMIT = 1000

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

ALLOWED_COLUMNS = get_parameter_value("SC_HCP_SCHEMA_COLUMNS")

# ----------------------
# Agent prompt: instructs how to build SQL from NLQ and what final JSON to produce
# ----------------------
PRESCRIBING_AGENT_PROMPT = f"""
You are the PrescribingAgent.

Your job: given a natural-language query (NLQ) about prescribing or a request to "prepare prescribing intelligence" for an HCP,
you must:
  1) Convert the NLQ to a single, safe SQL statement that queries the Redshift Serverless table `healthcare_data`.
  2) Use ONLY the allowed columns list embedded in your prompt (no other columns, no metadata).
  3) Always include a LIMIT clause when fetching multiple rows (use LIMIT {DEFAULT_SQL_LIMIT} unless NLQ specifies otherwise).
  4) Call the tool `execute_redshift_sql(sql_query, return_results=True)` to execute the SQL.
  5) Transform the returned rows into a single prescribing JSON object (schema defined below).
  6) Output ONLY the final JSON object - no SQL, no logs, no explanations.

Allowed columns (use only these):
{', '.join(ALLOWED_COLUMNS)}

--- WORKFLOW ---
STEP A:  From the NLQ, generate a safe SQL query that uses only the allowed columns:
    1. The table name is `healthcare_data`.
    2. You must only use these allowed columns:
    {", ".join(ALLOWED_COLUMNS)}
    3. Always produce a valid PostgreSQL SQL query.
    4. Never guess values not mentioned. If value is unclear, use placeholders:
        {{value}}
    5. Just select specific columns needed to answer the prompt, do NOT use SELECT *.
    6. stored this SQL query in the variable `sql_query`.
  If the NLQ asks for aggregated or territory-level results, generate appropriate SQL but do not exceed LIMIT {DEFAULT_SQL_LIMIT} for row results and only use columns above.

STEP B: After getting rows from execute_redshift_sql:
  - If no rows returned: return JSON:
    {{ "error": "No prescribing data found for the requested filters." }}
  - If a single row returned: compute the following prescribing block (use values directly or compute derived fields):
    prescribing {{
      Total Prescriptions(volume): {{ Last 7 days (trx_7d), Last 28 days (trx_28d), Last 90 days (trx_90d) }},
      New Prescriptions(new_rx): {{ Last 7 days (nrx_7d), Last 28 days (nrx_28d), Last 90 days (nrx_90d), New-to-Brand Prescriptions in last 28 days (nbrx_28d) }},
      Direction & Speed of change Prescriptions (momentum): {{ Week-Over-Week % Change in TRx in last 28 days (Total Prescriptions) (trx_28d_wow_pct), Quarter-Over-Quarter % Change in TRx in last 90 days (trx_90d_qoq_pct), New-to-Brand Rate in last 28 days (nbrx_28d_rate) }},
      pattern_classification: "<growing|declining|stable>",
      adoption_stage: brand adoption journey (adoption_stage_ordinal),
      Growth Potential (opportunity): {{ Gap to Monthly Prescription Goal (gap_to_goal_28d), Potential Uplift Score (potential_uplift_index) }},
      risk: {{ Probability the HCP will reduce or stop prescribing your brand in the next period (churn_risk_score), How open the HCP is expected to be to your next interaction (receptivity_score) }}
    }}

STEP C: Output ONLY the final JSON object with top-level keys:
- Always return only the final JSON as mentioned below and user readable short summary based on Prompt.
  {{
    "HcpId": "<id>",
    "Doctor Name":"<first_name, last_name>",
    "Specialty":"<specialty>",
    "Prescribing": {{
      Total Prescriptions(volume): {{ Last 7 days (trx_7d), Last 28 days (trx_28d), Last 90 days (trx_90d) }},
      New Prescriptions(new_rx): {{ Last 7 days (nrx_7d), Last 28 days (nrx_28d), Last 90 days (nrx_90d), New-to-Brand Prescriptions in last 28 days (nbrx_28d) }},
      Direction & Speed of change Prescriptions (momentum): {{ Week-Over-Week % Change in TRx in last 28 days (Total Prescriptions) (trx_28d_wow_pct), Quarter-Over-Quarter % Change in TRx in last 90 days (trx_90d_qoq_pct), New-to-Brand Rate in last 28 days (nbrx_28d_rate) }},
      Growth Potential (opportunity): {{ Gap to Monthly Prescription Goal (gap_to_goal_28d), Potential Uplift Score (potential_uplift_index) }},
      Risk: {{ Probability the HCP will reduce or stop prescribing your brand in the next period (churn_risk_score), How open the HCP is expected to be to your next interaction (receptivity_score) }},
      Brand adoption journey: "<adoption_stage_ordinal> (0: "Aware / Non-user", 1: "Considering", 2: "Trialing", 3: "Adopting", 4: "Champion", 5: "Regular User") Just print labels"
    }} 
  }}

--- Query Patterns ---
- For general retrieval: SELECT * FROM healthcare_data LIMIT 50;
- For filtering: SELECT * FROM healthcare_data WHERE <condition>;
- For sorting: ORDER BY <column> ASC/DESC;
- For aggregations: SELECT <col>, COUNT(*) FROM healthcare_data GROUP BY <col>;
- Multi-condition: Use AND / OR explicitly.

--- SAFETY & CONSTRAINTS ---
- Never leak raw SQL in agent output.
- Never call tools other than execute_redshift_sql.
- If returned data is stale (prescribing_freshness_days is large), include that value in the JSON but do not append commentary.


"""

# ----------------------
# Agent tools list and creation
# ----------------------
def _tools_list():
    return [execute_redshift_sql]

def create_prescribing_agent():
    return Agent(
        system_prompt=PRESCRIBING_AGENT_PROMPT,
        tools=_tools_list(),
    )

agent = create_prescribing_agent()

# ----------------------
# Runner
# ----------------------
def run_prescribing_agent(nlq: str):
    """
    Entrypoint: Pass an NLQ string describing the desired prescribing information.
    The agent will construct SQL, call execute_redshift_sql, and return the prescribing JSON.
    """
    instruction = nlq
    result = agent(instruction)
    # agent returns structured data from the LLM -> but per our system prompt the agent must return only the JSON object
    # Depending on Strands Agent implementation, result might be a string - ensure we parse/normalize:
    if isinstance(result, dict):
        return result
    try:
        # strip surrounding stuff and parse JSON
        parsed = json.loads(result)
        return parsed
    except Exception:
        # fallback: return raw agent result
        return {"status": "error", "message": "Agent did not return valid JSON", "raw": str(result)}

# ----------------------
# Example usage (local)
# ----------------------
if __name__ == "__main__":
    # quick manual test: replace with the NLQ you want
    nlq_example = input("Enter your prompt: ")
    out = run_prescribing_agent(nlq_example)
    