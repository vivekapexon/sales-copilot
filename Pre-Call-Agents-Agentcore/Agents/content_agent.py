# content_agent.py


import json
import logging
from typing import List, Any, Dict

from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# 🔁 Shared AgentCore utilities
from utilities.agentcore_utils import (
    get_parameter_value,
    bootstrap_workload_identity,
    parse_scopes,
    make_m2m_token_fetcher,
)

# Domain tools
from Tools.content_agent_tool import read_personalized_csv, analyze_hcps
from Tools.rag_tool import rag_lookup

# ----------------------------
# Basic config
# ----------------------------
REGION = "us-east-1"
WORKLOAD_NAME = "Sales-Copilet-Agents"  # keep same name as other agents

app = BedrockAgentCoreApp()
model = BedrockModel()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ----------------------------
# Identity bootstrap (AgentCore)
# ----------------------------
# This will fetch the workload access token from Identity and set it on
# BedrockAgentCoreContext so downstream AgentCore calls work consistently.
workload_access_token = bootstrap_workload_identity(
    workload_name=WORKLOAD_NAME,
    region=REGION,
)

# (Optional) If you later need M2M tokens for calling external APIs
# from inside tools, you can reuse this fetcher.
OAUTH_PROVIDER_NAME = get_parameter_value("PROVIDER_NAME", region=REGION)
OAUTH_SCOPE = parse_scopes(get_parameter_value("SCOPE", region=REGION) or "")
fetch_m2m_token = make_m2m_token_fetcher(
    provider_name=OAUTH_PROVIDER_NAME, # type: ignore
    scopes=OAUTH_SCOPE,
)

# ----------------------------
# Parameters / S3 config
# ----------------------------
CONTENT_AGENT_S3_CSV_URL = get_parameter_value(
    "CS_CONTENT_AGENT_S3_CSV_URL", region=REGION
)

if not CONTENT_AGENT_S3_CSV_URL:
    logger.warning("CS_CONTENT_AGENT_S3_CSV_URL not found in SSM Parameter Store.")

# ----------------------------
# Tools
# ----------------------------
def _tools_list() -> List[Any]:
    return [read_personalized_csv, analyze_hcps,rag_lookup]

# ----------------------------
# Content Agent Prompt
# ----------------------------
def create_content_agent() -> Agent:
    """
    Create the content agent with AgentCore-aware configuration.
    S3 URL is injected directly into the prompt so the LLM can reference it.
    """
    s3_url = CONTENT_AGENT_S3_CSV_URL or "<S3_CSV_URL_NOT_CONFIGURED>"

    system_prompt = f"""
    You are Content-Agent, an expert MOA & KOL engagement analyzer.

    DATA LOCATION:
    - The personalized HCP CSV is stored at:
      S3_URL = "{s3_url}"

    TOOLS:
    - read_personalized_csv(HCP_ID)
    - analyze_hcps(records, hcp_ids)
    - rag_lookup(query, top_k=5)

    DATA SOURCES & CITATIONS:
    - HCP profile & engagement data come from a CSV stored in S3 at S3_URL.
    - Approved scientific content (disease / MOA / safety / etc.) comes from the
      approved content search index (Amazon OpenSearch via rag_lookup).

    You MUST clearly expose these sources in the JSON output:
    - For every HCP result:
      - details.hcp_data_source MUST be:
        {{
          "type": "s3_csv",
          "uri": "{s3_url}"
        }}

      - If rag_lookup returns normal results (with "text" and "source"):
        * Summarize the most relevant snippets into details.rag_summary
        * Set details.rag_sources to a SHORT list of objects like:
          [
            {{"uri": "<title or URI from source>", "type": "opensearch"}},
            ...
          ]

      - If rag_lookup returns an item with "rag_status": "unavailable":
        * You MUST NOT invent or guess any approved material.
        * You MUST set:
            details.rag_summary = "Approved materials are currently unavailable."
            details.rag_sources = []
        * Still set details.hcp_data_source with the S3 CSV URI.

    If you never call rag_lookup, you MUST also set:
        details.rag_summary = "Approved materials are currently unavailable."
        details.rag_sources = []
        details.hcp_data_source = {{ "type": "s3_csv", "uri": "{s3_url}" }}

    Your workflow:
    1. Call read_personalized_csv(...) using S3_URL from the instructions.
    2. Select relevant hcp_ids and call analyze_hcps(...).
    3. If the user needs MOA/KOL/disease details or content suggestions, call rag_lookup(...).
    4. Build the final JSON.

    JSON format (PER HCP):
    [
      {{
        "hcp_id": str,
        "score": float,
        "rank": int,
        "reason": str,
        "details": {{
          "moa_email_summary": str,
          "clicked_kol_video_flag": str,
          "kol_video_summary": str,

          "rag_summary": str,
          "rag_sources": [
            {{
              "uri": str,
              "type": "opensearch"
            }}
          ],

          "hcp_data_source": {{
            "type": "s3_csv",
            "uri": "{s3_url}"
          }}
        }}
      }}
    ]

    Return ONLY the JSON array, no extra text.
    """

    return Agent(
        system_prompt=system_prompt,
        tools=_tools_list(),
        model=model,
    )


agent = create_content_agent()


# ----------------------------
# AgentCore entrypoint
# ----------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}) -> Dict[str, Any]:
    """
    Entrypoint for Bedrock AgentCore.

    payload example:
    {{
      "prompt": "Given HCP1000 provide approved materials"
    }}
    """
    instruction = payload.get(
        "prompt", "Given HCP1000 provide approved materials"
    )
    agent_result = agent(instruction)  # type: ignore

    # If you want to enforce JSON-only response, you can normalize here:
    # try:
    #     text = agent_result.message["content"][0]["text"]
    #     return json.loads(text)
    # except Exception:
    #     return {"status": "error", "raw": str(agent_result)}

    return agent_result


if __name__ == "__main__":
    app.run()
