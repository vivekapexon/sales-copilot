import json
from strands import Agent
from .Tools.execute_redshift_sql import execute_redshift_sql

# ----------------------
# Configuration 
# ----------------------
DATABASE = "sales_copilot_db"
DEFAULT_SQL_LIMIT = 1000


# ----------------------
# Allowed columns list (exact names from your table)
# ----------------------
ALLOWED_COLUMNS = [
    "hcp_id","doctor_first_name","doctor_last_name",
    "hco_id","territory_id","as_of_date","specialty_primary","subspecialty","practice_setting",
    "years_in_practice","hco_type","hco_size_bucket","hospital_affiliation_flag","kol_flag",
    "trx_7d","trx_28d","trx_90d","nrx_7d","nrx_28d","nrx_90d","nbrx_28d",
    "share_28d","share_90d","trx_28d_wow_pct","trx_90d_qoq_pct","share_28d_delta","nbrx_28d_rate",
    "comp_trx_share_28d","comp_share_28d_delta",
    "comp_detail_60d_cnt","comp_sample_60d_cnt","comp_event_90d_cnt","comp_formulary_win_30d_flag",
    "formulary_tier_score","prior_auth_required_flag","step_therapy_required_flag",
    "avg_time_to_fill_days_90d","patient_copay_median_90d","access_change_14d_flag","access_friction_index",
    "payer_top1_share_pct","payer_top3_share_pct",
    "calls_90d_cnt","meetings_90d_cnt","last_contact_days_ago",
    "meeting_accept_rate_90d","email_open_rate_60d","content_click_rate_60d",
    "sample_requests_90d_cnt","event_attendance_180d_cnt",
    "channel_pref_virtual_prob","channel_pref_inperson_prob",
    "monthly_goal_trx","gap_to_goal_28d","potential_uplift_index","launch_cohort_flag",
    "adoption_stage_ordinal","receptivity_score","churn_risk_score",
    "degree_centrality","betweenness_centrality","closeness_centrality",
    "peer_adoption_rate_90d","spillover_potential_index",
    "distance_km_from_homebase","drive_time_minutes",
    "morning_window_allowed_flag","afternoon_window_allowed_flag","clinic_saturday_open_flag",
    "parking_difficulty_score","sample_eligible_flag",
    "max_calls_per_28d","min_days_between_calls",
    "adverse_event_recent_flag","exclusion_list_flag",
    "weekofyear_sin","weekofyear_cos","month_sin","month_cos","recent_holiday_flag",
    "dow_1","dow_2","dow_3","dow_4","dow_5","dow_6","dow_7",
    "access_policy_change_7d_flag","payer_contract_change_30d_flag","competitor_launch_60d_flag","new_clinical_study_30d_flag",
    "rep_capacity_remaining_7d","travel_budget_remaining_28d","scheduled_calls_next_7d_cnt",
    "prescribing_freshness_days","access_freshness_days","engagement_freshness_days","feature_completeness_pct"
]

# ----------------------
# Agent prompt: instructs how to build SQL from NLQ and what final JSON to produce
# ----------------------
PRESCRIBING_AGENT_PROMPT = f"""
You are the PrescribingAgent.

Your job: given a natural-language query (NLQ) about prescribing or a request to "prepare prescribing intelligence" for an HCP,
you must:
  1) Convert the NLQ to a single, safe SQL statement that queries the Redshift Serverless table `healthcare_data` in database `{DATABASE}`.
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
    # print(json.dumps(out, indent=2))
    # sql_query = "SELECT * FROM healthcare_data WHERE doctor_first_name = 'Ashley'"
    # print(sql_query)
    # out = execute_redshift_sql(sql_query)
    # print(out)