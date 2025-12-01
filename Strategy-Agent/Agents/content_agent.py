import json
from typing import List, Any, Dict
from strands import Agent
from strands.models import BedrockModel
from .Tools.content_agent_tool import read_personalized_csv

from dotenv import load_dotenv
load_dotenv()
model = BedrockModel()
from .Tools.content_agent_tool import *
from .Tools.execute_redshift_sql import get_parameter_value

CONTENT_AGENT_S3_CSV_URL = get_parameter_value("CONTENT_AGENT_S3_CSV_URL")

# --- Agent wrapper ---
def _tools_list() -> List[Any]:
    return [read_personalized_csv, analyze_hcps]


agent = Agent(
    system_prompt="""
    You are Content-Agent, an expert MOA & KOL engagement analyzer for healthcare professionals (HCPs).

    New requirement:
    - ALWAYS start by calling the `read_personalized_csv` tool to load all HCP records.
    - After the tool returns data, use these records for filtering, selection, and engagement analysis.

    Your role:
    Given a user query (e.g., "oncology specialists with high video engagement" or 
    "HCPs who opened recent emails") and the loaded HCP records,
    intelligently select the most relevant HCPs by filtering/matching query keywords,
    criteria, or patterns across record fields 
    (specialty, location, moa_email_summary, kol_video_summary, engagement flags).

    Prioritize semantic relevance:
    - specialties
    - engagement levels (opened, clicked, watched >50%, etc.)
    - region/location
    - KOL or MOA behavior patterns

    Limit selection to 5–20 HCPs unless the query specifies otherwise.

    Process:
    1. Call `read_personalized_csv` to load all HCP data.
    2. Review the returned records to find relevant matches.
    3. Extract relevant hcp_ids.
    4. Call `analyze_hcps` with the selected hcp_ids to compute scores, ranks, and details.

    Output:
    - ONLY return a valid JSON array of analyzed HCPs sorted by score/rank descending.
    - Each item must be: 
      {"hcp_id": str, "score": float, "rank": int, "reason": str, "details": dict}

    Important:
    - No extra commentary or text outside the JSON.
    - Must follow tool-calling protocol.
    """,
    tools=_tools_list(),
)

# --- Runner ---
def run_content_agent(query: str) -> List[Dict[str, Any]]:
    print("Running Agent")
    records = read_personalized_csv(url=CONTENT_AGENT_S3_CSV_URL or "")  # Use env var; fallback if empty
    instruction = f"""
    User query: {query}
    HCP records provided: {json.dumps(records, indent=2)}  # Embedded for context; analyze directly.
    Select relevant HCPs, analyze engagement, and output ranked JSON array.
    """
    try:
        agent_result = agent(instruction, records=records)
        text_out = getattr(agent_result, "text", None) or str(agent_result)
        parsed = json.loads(text_out)
    except Exception as e:
        print(f"Agent failed: {e}. Falling back to keyword-based selection.")
        # Fallback: Keyword-based selection of HCP IDs (search across all record fields)
        selected_hcp_ids = []
        query_lower = query.lower()
        for record in records:
            record_text = ' '.join(str(v).lower() for v in record.values())
            if query_lower in record_text:
                hcp_id = record.get('hcp_id', '')
                if hcp_id:
                    selected_hcp_ids.append(str(hcp_id))
        selected_hcp_ids = list(set(selected_hcp_ids))  # Deduplicate
        parsed = analyze_hcps(records, selected_hcp_ids)
    return parsed

if __name__ == "__main__":
    # Test Case 1: Query for HCPs with MOA email opens 
    print("Test Case 1: Query for HCPs who opened MOA emails")
    result1 = run_content_agent("opened MOA email")
    print(json.dumps(result1, indent=2))

    # Test Case 2: Query for oncology specialists with video engagement
    print("\nTest Case 2: Query for oncology specialists with video clicks")
    result2 = run_content_agent("oncology clicked KOL video")
    print(json.dumps(result2, indent=2))

    # Test Case 3: General high-engagement query (broad selection)
    print("\nTest Case 3: Query for high engagement HCPs")
    result3 = run_content_agent("high engagement watched video")
    print(json.dumps(result3, indent=2))