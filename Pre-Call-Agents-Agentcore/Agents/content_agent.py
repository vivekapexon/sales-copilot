# content_agent.py
import json
from typing import List, Any, Dict
from strands import Agent
from strands.models import BedrockModel

model = BedrockModel()
# Importing external tools and helper functions
from .Tools.content_agent_tool import read_personalized_csv, analyze_hcps
from .Tools.execute_redshift_sql import get_parameter_value

# Getting Content Agnet S3 csv from the aws system manager parameter store.
# User Must have access to read this parameter.
CONTENT_AGENT_S3_CSV_URL = get_parameter_value("CS_CONTENT_AGENT_S3_CSV_URL")


# --- Agent wrapper making tools defined at one place ---
def _tools_list() -> List[Any]:
    return [read_personalized_csv, analyze_hcps]

# Main Content Agent definition for HCP selection and analysis. 
content_agent = Agent(
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
    - Include the data source table name also from where the data fetched
    - Each item must be: 
      {"hcp_id": str, "score": float, "rank": int, "reason": str, "details": dict}

    Important:
    - No extra commentary or text outside the JSON.
    - Must follow tool-calling protocol.
    """,
    tools=_tools_list(),
)


# --- Runner ---
def run_content_agent(query: str,csv_content_limit :int=10) -> List[Dict[str, Any]]:
    """
    Orchestrates the agent run such that the LLM is instructed to call:
    read_personalized_csv(url=CONTENT_AGENT_S3_CSV_URL,csv_content_limit)
     Args:
       query: str : User Query that needs to be passed to LLM
       csv_content_limit: limits the csv data to be passed to LLM, as it can break the LLM token limit

    The Agent runtime is expected to execute that tool call and return records back
    to the model. The model should then select HCPs and call analyze_hcps.
    """
    print("Running Content Agent (LLM-driven tool fetch)")
    s3_url = CONTENT_AGENT_S3_CSV_URL or ""
    if not s3_url:
        raise RuntimeError("CONTENT_AGENT_S3_CSV_URL is not set. Provide an S3 URL or set the env/parameter.")
    # Instruction: tell the model to call the tool first, and then to produce the final JSON.
    instruction = f"""
        S3_URL: {s3_url}
        csv_content_limit: {csv_content_limit}

        User query: {query}

        REQUIREMENTS:
        1) ALWAYS start by calling: read_personalized_csv(url=S3_URL,csv_content_limit=10).
        - The runtime will execute that tool and return the full list of records back to you.
        2) After the tool returns records, use those records to select the most relevant HCPs for the query.
        3) Then call analyze_hcps(records, hcp_ids) with the selected hcp_ids.
        4) Output ONLY the final analyzed JSON array (no extra commentary). Each item must be:
        {{"hcp_id": str, "score": float, "rank": int, "reason": str, "details": dict}}

        Constraints:
        - Limit selection to 5–20 HCPs unless the user query explicitly requests otherwise.
        - Use specialties, engagement flags, location, and kol video watch% as primary signals.
        - Do NOT embed or echo the CSV back into the output; return only the final analyzed JSON array.
        """

    try:
        agent_result = content_agent(instruction)
        text_out = getattr(agent_result, "text", None) or str(agent_result)
        return json.loads(text_out)
    
    except Exception as e:
        raise RuntimeError(f"Content Agent run failed: {e}")


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