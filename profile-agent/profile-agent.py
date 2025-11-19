# agents/profile_agent.py
"""
==========================================================
🧠 Profile Agent (NLQ Query Engine)
----------------------------------------------------------
1️⃣ Reads NLQ from prompt (natural language question)
2️⃣ Parses, understands intent, identifies columns & filters
3️⃣ Runs query on local CSV (for now)
4️⃣ Returns clean response in JSON or table format
----------------------------------------------------------
Future-ready for Aurora PostgreSQL backend.
==========================================================
"""

import json
import pandas as pd
import os
from strands import Agent, tool

# -----------------------------------------------------------
# 1) Setup: local CSV now, Aurora later
# -----------------------------------------------------------

LOCAL_DATA_PATH = r"C:\Users\nikhil.patil\Desktop\sales-copilot\profile-agent\HCP360.csv"  # update path if needed
df = pd.read_csv(LOCAL_DATA_PATH)


# -----------------------------------------------------------
# 2) Tools
# -----------------------------------------------------------

@tool
def query_local_profile_data(nlq: str) -> dict:
    """
    Execute an NLQ (Natural Language Query) against local CSV.
    Interprets column references, filters, and aggregates using pandas.
    Future version will connect to Aurora PostgreSQL instead.
    """
    print("Query", nlq)
    try:
        nlq_lower = nlq.lower()

        # crude column inference (extend with LLM/NL2SQL model later)
        if "average" in nlq_lower and "trx" in nlq_lower:
            result = df[["doctor_first_name", "doctor_last_name", "trx_28d"]].groupby(
                ["doctor_first_name", "doctor_last_name"]
            )["trx_28d"].mean().reset_index()
        elif "top" in nlq_lower and "specialty" in nlq_lower:
            result = (
                df.groupby("specialty_primary")
                .agg({"trx_28d": "sum"})
                .sort_values("trx_28d", ascending=False)
                .head(5)
                .reset_index()
            )
        elif "kol" in nlq_lower or "key opinion" in nlq_lower:
            result = df[df["kol_flag"] == 1][
                ["doctor_first_name", "doctor_last_name", "specialty_primary", "trx_28d"]
            ]
        elif "high trx" in nlq_lower or "most prescriptions" in nlq_lower:
            result = df.nlargest(5, "trx_28d")[
                ["doctor_first_name", "doctor_last_name", "specialty_primary", "trx_28d"]
            ]
        elif "average copay" in nlq_lower:
            avg_copay = df["patient_copay_median_90d"].mean()
            result = pd.DataFrame({"average_copay": [round(avg_copay, 2)]})
        elif "adoption stage" in nlq_lower:
            result = (
                df[["doctor_first_name", "doctor_last_name", "adoption_stage_ordinal"]]
                .sort_values("adoption_stage_ordinal", ascending=False)
                .head(10)
            )
        else:
            # fallback summary
            result = df.head(5)
            result["note"] = "Generic preview since no specific query intent matched."

        # convert to JSON-like dict
        return {"status": "success", "rows": result.to_dict(orient="records")}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# -----------------------------------------------------------
# 3) Agent Definition
# -----------------------------------------------------------

def _tools_list():
    return [query_local_profile_data]


def create_profile_agent():
    """
    ProfileAgent that interprets NLQs over HCP/HCO-level data.
    Returns clean JSON or tabular summaries of insights.
    """
    return Agent(
        system_prompt="""
        You are the ProfileAgent.

        Your purpose:
        - Understand any natural language question (NLQ) about HCP, HCO, TRx, NRx, share, access, or engagement data.
        - Run the correct query tool (`query_local_profile_data`).
        - Always output the result as a clean JSON or simple table.

        Logic:
        1. Detect intent from NLQ (filter, aggregate, rank, comparison, etc.)
        2. Route to local CSV query tool 
        3. Summarize the data meaningfully:
           - Show doctor names, specialties, key KPIs (trx, share, adoption, etc.)
           - Include contextual labels when relevant (top doctors, averages, trends)
        4. Output only JSON or markdown table — no code, logs, or explanations.

        Output Format Rules:
        - If multiple rows: show tabular JSON (list of dicts)
        - If single metric: show key-value JSON
        - Example:
          {
            "status": "success",
            "columns": ["doctor_first_name", "specialty_primary", "trx_28d"],
            "rows": [...]
          }
        """,
        tools=_tools_list(),
    )


# -----------------------------------------------------------
# 4) Main Execution
# -----------------------------------------------------------
def run_profile_agent(prompt: str):
    agent = create_profile_agent()
    response = agent(prompt)
    output_text = getattr(response, "text", str(response))
    print("Agent Output:", output_text)
    return output_text

# -----------------------------------------------------------
# 5) Local Test
# -----------------------------------------------------------

if __name__ == "__main__":
    #run_profile_agent("Show adoption stage of top performing doctors")
    run_profile_agent("Show who is specialist in cardiology")
    # run_profile_agent("What is the average copay across all doctors?")
    #run_profile_agent("Show doctors with highest TRx in last 28 days")

