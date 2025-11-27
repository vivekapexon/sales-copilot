import json
from typing import List, Any, Dict
import os
from strands import Agent
from strands.models import BedrockModel
from dotenv import load_dotenv
load_dotenv()
model = BedrockModel()
from .Tools.content_agent_tool import *
# Load S3-related environment variables
content_agent_S3_csv_url = os.environ.get("CONTENT_AGENT_S3_CSV_URL")
aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
aws_region = os.environ.get("AWS_REGION")


# --- Agent wrapper ---
def _tools_list() -> List[Any]:
    return [read_personalized_csv, analyze_hcps]

agent = Agent(
        system_prompt="""
        You are Content-Agent, an expert MOA & KOL engagement analyzer for healthcare professionals (HCPs).
        
        Your role: Given a user query (e.g., "oncology specialists with high video engagement" or "HCPs who opened recent emails") and HCP records,
        intelligently select the most relevant HCPs by filtering/matching query keywords, criteria, or patterns across record fields 
        (e.g., specialty, name, location, moa_email_summary, kol_video_summary, engagement flags).
        Prioritize semantic relevance: match specialties, engagement levels (e.g., "opened", "watched >50%"), or other attributes.
        Limit selection to 5-20 HCPs unless query specifies otherwise to ensure focused analysis.
        Then, analyze their engagement using available tools, scoring based on MOA opens/clicks and KOL video interactions.
        
        Process:
        1. Review records for matches to query.
        2. Extract relevant hcp_ids.
        3. Use analyze_hcps tool to compute scores, ranks, and details.
        4. Output ONLY a valid JSON array of analyzed HCPs, sorted by rank/score descending. 
           Each item: {"hcp_id": str, "score": float, "rank": int, "reason": str, "details": dict}.
        
        Be precise, efficient, and ensure output is parseable JSON—no extra text.
        """,
        tools=_tools_list(),
    )

# --- Runner ---
def run_content_agent(query: str) -> List[Dict[str, Any]]:
    print("Running Agent")
    records = read_personalized_csv(url=content_agent_S3_csv_url or "")  # Use env var; fallback if empty
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