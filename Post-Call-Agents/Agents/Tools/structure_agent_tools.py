#/post_call/Agents/Tools/structure_agent_tools.py
import json
import boto3
from typing import Dict, Any
from strands import tool
from .execute_redshift_sql import execute_redshift_sql
import pandas as pd
# AWS clients 
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name= "us-east-1")

# Set this to your transcripts table in Redshift
TRANSCRIPT_TABLE = "public.voice_to_crm"  # <-- update to your actual schema.table

TRANSCRIPTION_BUCKET = "sales-copilot-bucket"
RESULT_BUCKET = "sales-copilot-bucket"
CSV_BUCKET="sales-copilot-bucket"
S3_DEMO_TRASNCRPTION_JSON_FILE="transcripts/voice_to_crm.csv"

@tool
def save_structured_note(key: str, note: Dict[str, Any]) -> str:
    """Save the structured note to S3 bucket."""
    result_key = key.replace("transcriptions/", "notes/", 1)
    if result_key.endswith(".json"):
        result_key = result_key.replace(".json", "_note.json")
    else:
        result_key += "_note.json"

    s3.put_object(
        Bucket=RESULT_BUCKET,
        Key=result_key,
        Body=json.dumps(note, indent=2),
        ContentType="application/json"
    )
    return f"Saved to s3://{RESULT_BUCKET}/{result_key}"


@tool
def load_transcription_data_from_redshift(hcp_id: str) -> str:
    """
    Load a transcript text row from Redshift for the specified HCP ID and return it as a JSON string.

    Behavior:
      - Queries Redshift using the execute_redshift_sql tool.
      - Returns a JSON string of the first matching row (or an error JSON).
      - Keep TRANSCRIPT_TABLE updated to the correct schema.table.

    Args:
        hcp_id: The HCP ID to filter and retrieve the specific row for.

    Returns:
        JSON string: either the row dict or {"error": "..."}.
    """
    # Basic sanitization to reduce risk of SQL injection; prefer parameterized execution if available
    if hcp_id is None:
        return json.dumps({"error": "hcp_id is required"})

    # Escape single quotes (simple mitigation)
    safe_hcp_id = str(hcp_id).replace("'", "''")

    sql = f"""
    SELECT *
    FROM {TRANSCRIPT_TABLE}
    WHERE hcp_id = '{safe_hcp_id}'
    LIMIT 1;
    """.strip()

    print(f"Querying Redshift table {TRANSCRIPT_TABLE} for HCP ID: {hcp_id}")

    try:
        resp = execute_redshift_sql(sql, return_results=True)
    except Exception as e:
        return json.dumps({"error": f"execute_redshift_sql call failed: {str(e)}"})

    # Resp expected shape: {"status":"finished","rows":[{col:val,...}, ...], ...} or error structure
    if not isinstance(resp, dict):
        return json.dumps({"error": "Unexpected response from execute_redshift_sql"})

    status = resp.get("status")
    if status != "finished":
        # pass along error/message if present
        msg = resp.get("message", f"Redshift statement status: {status}")
        return json.dumps({"error": msg})

    rows = resp.get("rows", [])
    if not rows:
        return json.dumps({"error": f"No row found for HCP ID: {hcp_id}"})

    # Return the first matching row (to mirror the original S3 loader behavior)
    row_data = rows[0]

    # Ensure JSON-serializable values (convert non-serializable to strings)
    try:
        json.dumps(row_data)  # quick test
    except TypeError:
        # convert problematic values to strings
        for k, v in list(row_data.items()):
            try:
                json.dumps(v)
            except TypeError:
                row_data[k] = str(v)

    return json.dumps(row_data)
