import os
import json
import time
from typing import List, Dict, Any, Optional
import boto3
from strands import Agent, tool
from strands.models import BedrockModel
from botocore.exceptions import ClientError
from botocore.config import Config
from datetime import datetime, timezone


# Environment variables expected:
# - BRIEF_S3_BUCKET        -> bucket name where briefs are stored (versioning recommended)
# - BRIEF_S3_PREFIX        -> optional prefix/folder in bucket (e.g. "briefs/")
# - DDB_TABLE_NAME         -> DynamoDB table for current briefs (PK: brief_id)
# - AWS_REGION             -> AWS region
# - BEDROCK_MODEL_ID       -> optional model identifier for Bedrock (if needed)

BRIEF_S3_BUCKET = os.getenv("BRIEF_S3_BUCKET")
BRIEF_S3_PREFIX = os.getenv("BRIEF_S3_PREFIX", "").strip("/")
DDB_TABLE_NAME = os.getenv("DDB_TABLE_NAME")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", None)
BEDROCK_MODEL_CONTENT_TYPE = os.getenv("BEDROCK_MODEL_CONTENT_TYPE", "text/plain")  # or application/json
BEDROCK_MODEL_ACCEPT = os.getenv("BEDROCK_MODEL_ACCEPT", "application/json")  # what the model returns

session = boto3.Session(region_name=AWS_REGION)
s3_client = session.client("s3")
dynamodb = session.resource("dynamodb", region_name=AWS_REGION) if DDB_TABLE_NAME else None
# Optional custom client config (retries, timeouts)
_boto_config = Config(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=10, read_timeout=120)

# Create the bedrock runtime client
bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=_boto_config)


# --- Helpers ---
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _s3_key_for_brief(brief_id: str) -> str:
    """Return a safe S3 key (prefix + timestamped filename)."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = f"{brief_id}_{ts}.json"
    return f"{BRIEF_S3_PREFIX}/{filename}" if BRIEF_S3_PREFIX else filename


# Tools:

@tool
def load_kb_metadata(kb_s3_url: Optional[str] = None, max_items: int = 50) -> Dict[str, Any]:
    """
    Load KB metadata to be used as citations. Supports:
      - S3 JSONL/JSON files pointed by kb_s3_url (s3://bucket/key)

    Returns:
      dict with 's3_docs': [...], 'opensearch_docs': [...]
    Notes:
      - This function returns small snippets/metadata only (not entire docs) to include in prompts.
      - For production, prefer fetching only the passages referenced by the retriever.
    """
    results: Dict[str, Any] = {"s3_docs": [], "opensearch_docs": []}

    # 1) fetch from S3 (if provided)
    if kb_s3_url and kb_s3_url.startswith("s3://"):
        without = kb_s3_url[len("s3://"):]
        bucket, key = without.split("/", 1)
        try:
            obj = s3_client.get_object(Bucket=bucket, Key=key)
            raw = obj["Body"].read()
            # Try JSON, fallback to JSONL lines
            try:
                data = json.loads(raw)
                # If list-like, take up to max_items
                if isinstance(data, list):
                    results["s3_docs"] = data[:max_items]
                elif isinstance(data, dict):
                    results["s3_docs"] = [data]
                else:
                    results["s3_docs"] = []
            except Exception:
                # Try JSONL: each line a JSON doc
                lines = raw.decode("utf-8").splitlines()
                docs = []
                for line in lines[:max_items]:
                    try:
                        docs.append(json.loads(line))
                    except Exception:
                        continue
                results["s3_docs"] = docs
        except ClientError as e:
            raise RuntimeError(f"Error fetching KB from S3: {e}")

    return results

@tool
def synthesize_brief(
    agent_outputs: List[Dict[str, Any]],
    kb_context: Dict[str, Any],
    brief_id: Optional[str] = None,
    length: str = "concise"
) -> Dict[str, Any]:
    """
    Synthesize multiple agent outputs + KB context into a single Brief using Bedrock LLM.

    Inputs:
      - agent_outputs: list of dicts (each agent's payload)
      - kb_context: output from load_kb_metadata (containing 's3_docs' and/or 'opensearch_docs')
      - brief_id: optional identifier; if not provided, one will be generated
      - length: "concise" | "detailed" controls LLM instruction

    Returns:
      - A Brief JSON dict with structure (example):
        {
          "brief_id": "brief-2025-11-24-1234",
          "created_at": "...",
          "summary": "...",
          "action_items": [...],
          "citations": [...],
          "agent_payloads": [...],
          "raw_brief_text": "...",
          "meta": { ... }
        }

    """
    if not brief_id:
        brief_id = f"brief-{int(time.time())}"

    # Prepare a compact prompt with the payloads and KB excerpts
    # Limit the prompt size in real deployments - pass only extracted passages / citations.
    agent_snippets = []
    for i, p in enumerate(agent_outputs, start=1):
        # Turn into a short single-line snippet for the prompt; keep original payload in final JSON
        snippet = f"Agent[{i}]: id={p.get('agent_id','unknown')}; type={p.get('type','unknown')}; summary={p.get('summary', p)}"
        agent_snippets.append(snippet)

    # Build citation list to include in the prompt
    kb_snippets = []
    for s in kb_context.get("s3_docs", [])[:10]:
        title = s.get("title") if isinstance(s, dict) else None
        excerpt = s.get("excerpt") or s.get("text") or str(s)[:300]
        kb_snippets.append(f"{title or 's3_doc'}: {excerpt}")

    prompt = f"""
        You are a concise synthesis assistant. Produce a JSON Brief that:
        - synthesizes the following agent outputs (listed).
        - cites KB passages provided.
        - produces: brief_id, created_at, top_findings (list), recommended_action_items (list),
        evidence_citations (list of {{"source_id","title","publisher","date","excerpt"}}), confidence_score (0-1),
        and a human_readable_brief_text.

        Synthesis length: {length}

        Agent payloads (one per line):
        {agent_snippets}

        KB excerpts (one per line):
        {kb_snippets}

        Important:
        - For each top finding include which agent(s) contributed to it (by index), and cite relevant KB excerpts by source_id.
        - Return ONLY valid JSON parsable output. Do not include explanation outside the JSON.
        """

    try:
        model_response_text = None
        try:
            
            model_response_text=bedrock_client.invoke_model(body=prompt,modelId=BEDROCK_MODEL_ID)
        except Exception:
            raise RuntimeError(f"BedrockModel invocation failed")

        try:
            brief_json = json.loads(model_response_text)
        except Exception:
            
            raise ValueError("LLM output did not contain JSON.")

    except Exception as e:
        raise RuntimeError(f"Synthesis failed: {e}")

    # Normalize / add meta fields
    brief_json.setdefault("brief_id", brief_id)
    brief_json.setdefault("created_at", _now_iso())
    brief_json.setdefault("agent_payloads", agent_outputs)
    brief_json.setdefault("kb_context_summary", {"s3_count": len(kb_context.get("s3_docs", [])), "opensearch_count": len(kb_context.get("opensearch_docs", []))})
    brief_json.setdefault("meta", {"synth_method": "bedrock", "synth_prompt_length_chars": len(prompt)})

    return brief_json

@tool
def persist_brief(brief: Dict[str, Any], s3_bucket: Optional[str] = None, ddb_table_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Persist the synthesized Brief to DynamoDB (current) and S3 (archived/versioned).
    - DynamoDB: upsert item with PK=brief_id, write timestamp, and minimal indexed fields.
    - S3: upload the full brief JSON (use bucket versioning to maintain history).
    Returns metadata about persisted locations.
    """
    s3_bucket = s3_bucket or BRIEF_S3_BUCKET
    ddb_table_name = ddb_table_name or DDB_TABLE_NAME

    if not s3_bucket:
        raise RuntimeError("S3 bucket not configured (BRIEF_S3_BUCKET).")
    # Save to S3
    brief_id = brief.get("brief_id") or f"brief-{int(time.time())}"
    key = _s3_key_for_brief(brief_id)

    try:
        s3_client.put_object(Bucket=s3_bucket, Key=key, Body=json.dumps(brief, indent=2).encode("utf-8"), ContentType="application/json")
        s3_location = {"bucket": s3_bucket, "key": key}
    except ClientError as e:
        raise RuntimeError(f"Failed to write brief to S3: {e}")

    # Save current to DynamoDB (if provided)
    ddb_result = None
    if ddb_table_name:
        table = dynamodb.Table(ddb_table_name)#type:ignore
        item = {
            "brief_id": brief_id,
            "updated_at": _now_iso(),
            "summary": brief.get("summary") or brief.get("top_findings", []),
            "confidence_score": brief.get("confidence_score", 1.0),
            "s3_bucket": s3_bucket,
            "s3_key": key
        }
        try:
            table.put_item(Item=item)
            ddb_result = {"table": ddb_table_name, "item": {"brief_id": brief_id}}
        except ClientError as e:
            raise RuntimeError(f"Failed to put item into DynamoDB: {e}")

    return {"s3": s3_location, "dynamodb": ddb_result}

# Agent wrapper
def _tools_list():
    return [load_kb_metadata, synthesize_brief, persist_brief]


Strategy_agent = Agent(
    system_prompt="""
You are a regulated sales assistant. Use ONLY the provided structured inputs and the explicitly linked evidence to produce a short, actionable Pre-Call Brief for a field representative. Always include evidence source_ids for every factual claim or recommendation. Do NOT invent facts or cite sources not in the input. If critical inputs are missing, list them and give a conservative fallback. Output ONLY valid JSON conforming to the Brief schema.
""",
    tools=_tools_list(),
)

def run_strategy_agent(agent_outputs: List[Dict[str, Any]], kb_s3_url: Optional[str] = None, brief_id: Optional[str] = None):
    """
    Orchestration helper to run the agent end-to-end:
     1) load kb metadata
     2) synthesize brief
     3) persist brief
    """
    kb_ctx = load_kb_metadata(kb_s3_url=kb_s3_url)
    brief = synthesize_brief(agent_outputs=agent_outputs, kb_context=kb_ctx, brief_id=brief_id)
    persist_info = persist_brief(brief)
    return {"brief": brief, "persist_info": persist_info}
