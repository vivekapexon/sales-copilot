
import json
import re
from typing import List, Any, Dict

import os
from strands import Agent
from strands.models import BedrockModel
from dotenv import load_dotenv
load_dotenv()
model =BedrockModel()
from utilities.logger import logger
from tools.content_agent_tools import *
# Load S3-related environment variables
content_agent_S3_csv_url = os.environ.get("CONTENT_AGENT_S3_CSV_URL")
aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
aws_region = os.environ.get("AWS_REGION")


# --- Agent wrapper ---
def _tools_list() -> List[Any]:
    return [read_personalized_csv, analyze_hcps, save_json]

agent = Agent(
        system_prompt="""
        You are Content-Agent (MOA & KOL engagement analyzer).
        Analyze HCP engagement and output a ranked JSON array.
        """,
        tools=_tools_list(),
    )

# --- Runner ---
def run_content_agent(hcp_ids: List[str]) -> List[Dict[str, Any]]:
    print("Running Agent")
    records = read_personalized_csv(url="https://localhost")
    print(f"Showing csv records{records}")
    instruction = "Analyze and return ranked JSON array for the given hcp_ids."
    
    try:
        agent_result = agent(instruction, records=records, hcp_ids=hcp_ids)
        text_out = getattr(agent_result, "text", None) or str(agent_result)
        parsed = json.loads(text_out)
    except Exception:
        parsed = analyze_hcps(records, hcp_ids)

    save_json(parsed, OUTPUT_FILE)
    return parsed

if __name__ == "__main__":
	pass
