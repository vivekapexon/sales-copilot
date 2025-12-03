import json
from strands import Agent, tool
from .Tools.execute_redshift_sql import execute_redshift_sql

# ---------------------------------------------------
# 0) HCP Table Schema
# ---------------------------------------------------
HCP_SCHEMA_COLUMNS = [
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

# ---------------------------------------------------
# 2) Agent Definition
# ---------------------------------------------------

def _tools_list():
    return [execute_redshift_sql]


def create_profile_agent():
    """Agent that generates PostgreSQL queries from natural language."""
    return Agent(
        system_prompt=f"""
            You are the ProfileAgent.
            Your task is to generate PostgreSQL SELECT queries from natural-language user prompts.

            Rules:
            1. The table name is `healthcare_data`.
            2. You must only use these allowed columns:
            {", ".join(HCP_SCHEMA_COLUMNS)}
            3. Always produce a valid PostgreSQL SQL query.
            4. Never guess values not mentioned. If value is unclear, use placeholders:
                {{value}}
            5. Just select specific columns needed to answer the prompt, do NOT use SELECT *.
            6. stored this SQL query in the variable `sql_query`.
            7. Pass created SQL query to the tool `execute_redshift_sql(sql_query)` for execution.
            8. If user asks for something impossible with the schema, return:
            {{
                "sql_query": "UNSUPPORTED_QUERY"
            }}

            Strict Output Rules:
            - Always return the final answer as a simple JSON object as per user request.
            - No need to print all columns just display the columns which shows the details asked in the prompt.
            - If multiple rows, return as list of dicts.
            - If single metric, return as key-value pair.
            - Add simple two liner explanations if needed.
            - No other columns except those requested,No SQL, no logs.

            Query Patterns:
            - For general retrieval: SELECT * FROM healthcare_data LIMIT 50;
            - For filtering: SELECT * FROM healthcare_data WHERE <condition>;
            - For sorting: ORDER BY <column> ASC/DESC;
            - For aggregations: SELECT <col>, COUNT(*) FROM healthcare_data GROUP BY <col>;
            - Multi-condition: Use AND / OR explicitly.
            
            You must always generate the most reasonable SQL based on the user's text.
        """,
        tools=_tools_list(),
    )


# ---------------------------------------------------
# 3) Main Runner
# ---------------------------------------------------

def run_main_agent(prompt: str):
    agent = create_profile_agent()
    result = agent(prompt)
    print("Generated SQL:", result)
    return result


# ---------------------------------------------------
# 4) Local Execution
# ---------------------------------------------------
if __name__ == "__main__":
    prompt = input("Enter your prompt: ")
    run_main_agent(prompt)