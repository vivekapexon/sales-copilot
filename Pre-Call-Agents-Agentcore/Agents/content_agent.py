import json
import logging
import re
import os
import boto3
import pandas as pd
import io
from typing import List, Any, Dict, Union
from strands import  tool
from typing import List, Dict, Any
from strands import tool
import logging
from typing import List, Any, Dict
from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# 🔁 Shared AgentCore utilitie
# Domain tools

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

# (Optional) If you later need M2M tokens for calling external APIs
# from inside tools, you can reuse this fetcher.
def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager
      Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or
        None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store.
         Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3
            bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm", region_name="us-east-1")
        response = ssm_client.get_parameter(
            Name=parameter_name, WithDecryption=True
            )
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None

# ----------------------------
# Parameters / S3 config
# ----------------------------
CONTENT_AGENT_S3_CSV_URL = get_parameter_value("CS_CONTENT_AGENT_S3_CSV_URL")

SALES_COPILOT_BEDROCK_EMBED_MODEL = get_parameter_value("SALES_COPILOT_BEDROCK_EMBED_MODEL")
SALES_COPILOT_AOSS_ENDPOINT = get_parameter_value("SALES_COPILOT_AOSS_ENDPOINT")
SALES_COPILOT_INDEX_NAME = get_parameter_value("SALES_COPILOT_INDEX_NAME")
VECTOR_DIM = int("1024")

# Bedrock client (for embeddings)
bedrock = boto3.client("bedrock-runtime", region_name=REGION)


def _aoss_client() -> OpenSearch:
    """
    Initialize OpenSearch Serverless (vector collection) client using IAM SigV4.
    """
    if not SALES_COPILOT_AOSS_ENDPOINT:
        raise RuntimeError("AOSS_ENDPOINT not set. Please configure it in .env")

    host = SALES_COPILOT_AOSS_ENDPOINT.replace("https://", "").replace("http://", "")

    session = boto3.Session()
    creds = session.get_credentials()
    auth = AWSV4SignerAuth(creds, REGION, service="aoss")

    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=60,
        max_retries=3,
        retry_on_timeout=True,
    )
    logging.info(f"[rag_common] Using AOSS endpoint: {SALES_COPILOT_AOSS_ENDPOINT}")
    logging.info(f"[rag_common] Using index name:    {SALES_COPILOT_INDEX_NAME}")
    
    return client


os_client = _aoss_client()


def embed_text(text: str) -> list[float]:
    """
    Call Amazon Bedrock embedding model to convert text into a vector.
    """
    body = {"inputText": text}
    resp = bedrock.invoke_model(
        modelId=SALES_COPILOT_BEDROCK_EMBED_MODEL,
        body=json.dumps(body),
        accept="application/json",
        contentType="application/json",
    )
    resp_body = json.loads(resp["body"].read())
    emb = resp_body.get("embedding")
    if not emb:
        raise ValueError("Embedding model returned no vector")
    return emb

@tool
def rag_lookup(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Semantic RAG over approved materials using OpenSearch Serverless vector collection.
    """
    logging.info(f"[rag_lookup] query={query!r}, top_k={top_k}")

    # 1) Embed query
    try:
        query_vec = embed_text(query)
        logging.info(f"[rag_lookup] embedding length={len(query_vec)}")
    except Exception as e:
        logging.error(f"[rag_lookup] embed_text failed: {e}")
        return [{"rag_status": "unavailable"}]

    # 2) kNN search
    body = {
        "size": top_k,
        "query": {
            "knn": {
                "embedding": {
                    "vector": query_vec,
                    "k": top_k
                }
            }
        }
    }

    try:
        resp = os_client.search(index=SALES_COPILOT_INDEX_NAME, body=body)
        logging.info(f"[rag_lookup] search took: {resp.get('took')} ms")
    except Exception as e:
        logging.error(f"[rag_lookup] os_client.search failed: {e}")
        return [{"rag_status": "unavailable"}]

    hits = resp.get("hits", {}).get("hits", [])
    logging.info(f"[rag_lookup] hits count: {len(hits)}")

    if not hits:
        return [{"rag_status": "unavailable"}]

    results: List[Dict[str, Any]] = []
    for h in hits:
        src = h.get("_source", {})
        results.append(
            {
                "text": src.get("text", ""),
                "score": h.get("_score"),
                "source": {
                    "uri": src.get("title", ""),
                    "type": "opensearch"
                }
            }
        )

    return results



def _is_s3_url(u: str) -> bool:
    """
    Return True if the given string is an S3 URL of the form 's3://...'.

    Parameters:
        u: The input string to check.

    Returns:
        True if the string starts with 's3://', otherwise False.
    """
    return bool(u) and u.startswith("s3://")

def _extract_percent(text: str) -> float:
    """
    Extract a percentage value from a text string.

    Parameters:
        text: A string potentially containing a percentage such as 'Watched 45%'.

    Returns:
        The numeric percentage as a float (0–100), or 0.0 if no valid
        percentage is found.
    """
    if not text:
        return 0.0

    m = re.search(r"(\d{1,3})%", text)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return 0.0

    return 0.0


@tool
def read_personalized_csv(HCP_ID: Union[str, List[str], None] = None) -> List[Dict[str, Any]]:
    """
    Returns:
     
      - Single row (if HCP_ID = "HCP1003")
      - Multiple rows (if HCP_ID = ["HCP1001","HCP1002"])
    """
    url=get_parameter_value("CS_CONTENT_AGENT_S3_CSV_URL")
    # --- Load from S3 ---
    if _is_s3_url(url): # type: ignore
        print(f"Using S3 for csv file: {url}")
        without_prefix = url[len("s3://"):]# type: ignore
        bucket, key = without_prefix.split("/", 1)

        try:
            s3 = boto3.client("s3", region_name="us-east-1")
            obj = s3.get_object(Bucket=bucket, Key=key)

            raw_bytes = obj["Body"].read()
            df = pd.read_csv(io.BytesIO(raw_bytes), dtype=str)
            df = df.fillna("")

            # -------------------------------
            # Apply HCP filtering logic
            # -------------------------------
            if HCP_ID is None or HCP_ID == "" or HCP_ID == []:
                return df.to_dict(orient="records")#type:ignore

            # Convert comma-separated string to list
            if isinstance(HCP_ID, str):
                if "," in HCP_ID:
                    HCP_ID = [x.strip() for x in HCP_ID.split(",")]
                else:
                    HCP_ID = [HCP_ID]

            # Filter using the actual column name "hcp_id"
            filtered_df = df[df["hcp_id"].isin(HCP_ID)]

            return filtered_df.to_dict(orient="records")#type:ignore

        except s3.exceptions.NoSuchKey:
            raise FileNotFoundError(f"S3 key not found: s3://{bucket}/{key}")
        except s3.exceptions.NoSuchBucket:
            raise FileNotFoundError(f"S3 bucket not found: {bucket}")
        except Exception as e:
            raise RuntimeError(f"Error reading S3 CSV: {e}")

    raise FileNotFoundError("No CSV found. Provide an S3 URL.")


@tool
def analyze_hcps(records: List[Dict[str, Any]], hcp_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Analyze, score, and rank HCPs based on their engagement with MOA emails
    and KOL video content.

    Use this tool for below:
      - scoring 1 or more HCPs by engagement behavior,
      - ranking HCPs based on MOA email opens, clicks, or video watch %, or
      - a structured summary of HCP engagement from raw CRM activity logs.

    Expected Inputs:
        records:
            A list of dictionaries, each representing an HCP’s activity record.
            Each record should contain:
                - "hcp_id": str or int
                - "moa_email_summary": str (e.g., "Opened", "Delivered")
                - "clicked_kol_video_flag": "Yes" / "No"
                - "kol_video_summary": str containing a watch percentage like "Watched 43%"
        hcp_ids:
            A list of HCP identifiers (string or numeric) that should be evaluated.

    Scoring Logic:
        - +1.0  if "opened" appears in MOA email summary
        - +0.5  if MOA summary exists but does not include "opened"
        - +2.0  if the KOL video click flag is "yes"
        - +((watch_percent / 100) * 2.0) based on extracted KOL video watch %

    Output:
        A list of dictionaries, one per HCP, each containing:
            - "hcp_id": str
            - "score": numeric total engagement score
            - "rank": ordinal ranking (1 = highest score); None if not found
            - "reason": human-readable explanation of scoring
            - "details": original engagement fields for transparency

        HCPs not found in the records list are included at the end with:
            - score = 0.0
            - rank = None
            - reason = "HCP id not found"

    Returns:
        A fully ranked list of HCP engagement analyses, sorted by score
        (descending), with missing HCPs appended last.
    """
    rows = {str(r.get("hcp_id")): r for r in records}
    results = []

    for h in hcp_ids:
        h = str(h)
        r = rows.get(h)

        if not r:
            results.append({
                "hcp_id": h,
                "rank": None,
                "score": 0.0,
                "reason": "HCP id not found",
                "details": {}
            })
            continue

        moa = r.get("moa_email_summary", "") or ""
        clicked = (r.get("clicked_kol_video_flag", "").strip().lower() == "yes")
        kol_summary = r.get("kol_video_summary", "") or ""

        score = 0.0
        reasons = []

        if "opened" in moa.lower():
            score += 1.0
            reasons.append("Opened MOA email")
        elif moa.strip():
            score += 0.5
            reasons.append("MOA email interaction")

        if clicked:
            score += 2.0
            reasons.append("Clicked/Watched KOL video")

        pct = _extract_percent(kol_summary)
        if pct > 0:
            add = (pct / 100) * 2.0
            score += add
            reasons.append(f"KOL video watched {pct}%")

        results.append({
            "hcp_id": h,
            "score": round(score, 3),
            "rank": None,
            "reason": "; ".join(reasons) if reasons else "No clear engagement",
            "details": {
                "moa_email_summary": moa,
                "clicked_kol_video_flag": r.get("clicked_kol_video_flag", ""),
                "kol_video_summary": kol_summary,
            }
        })

    # Rank by score (descending)
    ranked = sorted(
        [x for x in results if x["reason"] != "HCP id not found"],
        key=lambda z: z["score"],
        reverse=True
    )

    for i, item in enumerate(ranked, start=1):
        item["rank"] = i

    # Append missing HCPs
    not_found = [x for x in results if x["reason"] == "HCP id not found"]

    return ranked + not_found


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
