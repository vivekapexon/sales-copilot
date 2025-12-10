#structure agent.py
import json
from strands import Agent,tool
import boto3
from typing import Dict, Any
import time
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name= "us-east-1")
import logging
from bedrock_agentcore.runtime import BedrockAgentCoreApp
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compilance_agent")
s3_client = boto3.client("s3")
app = BedrockAgentCoreApp()

def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store. Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3 bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None

# ----------------------
# Configuration 
# ----------------------
WORKGROUP = "sales-copilot-workgroup"
DATABASE = "sales_copilot_db"
SECRET_ARN = (
    "arn:aws:secretsmanager:us-east-1:969385807621:"
    "secret:redshift!sales-copilot-namespace-sales_copilot_admin-seNjuJ"
)

# Optional: set a default row limit for arbitrary SQL to avoid accidental full-table scans
DEFAULT_SQL_LIMIT = 1000
SQL_POLL_INTERVAL_SECONDS = 0.5
SQL_POLL_MAX_SECONDS = 30.0

# ----------------------
# Helper: Redshift Data API tool
# ----------------------
@tool
def execute_redshift_sql(sql_query: str, return_results: bool = True) -> Dict[str, Any]:
    """
    Execute arbitrary SQL against Redshift Serverless Data API (workgroup mode).
    Returns a dict: {"status":"finished","rows":[{col:val,...}, ...]} or error structure.

    - sql_query: SQL string to execute (caller is responsible for safety/validation).
    - return_results: when False, only returns execution status.
    """
    client = boto3.client("redshift-data")
    try:
        resp = client.execute_statement(
            WorkgroupName=WORKGROUP,
            Database=DATABASE,
            SecretArn=SECRET_ARN,
            Sql=sql_query
        )
        stmt_id = resp["Id"]
    except Exception as e:
        return {"status": "error", "message": f"execute_statement error: {str(e)}"}

    # Poll for completion
    elapsed = 0.0
    while elapsed < SQL_POLL_MAX_SECONDS:
        try:
            status_resp = client.describe_statement(Id=stmt_id)
            status = status_resp.get("Status")
        except Exception as e:
            return {"status": "error", "message": f"describe_statement error: {str(e)}"}
        if status in ("FINISHED", "ABORTED", "FAILED"):
            break
        time.sleep(SQL_POLL_INTERVAL_SECONDS)
        elapsed += SQL_POLL_INTERVAL_SECONDS

    if status != "FINISHED":
        # Try to return error details if available
        try:
            status_resp = client.describe_statement(Id=stmt_id)
            return {"status": status, "message": status_resp.get("Error")}
        except Exception:
            return {"status": status, "message": "Statement did not finish within time limit."}

    if not return_results:
        return {"status": "finished", "statement_id": stmt_id}

    # Retrieve results
    try:
        results = client.get_statement_result(Id=stmt_id)
    except Exception as e:
        return {"status": "error", "message": f"get_statement_result error: {str(e)}"}

    column_info = [c["name"] for c in results.get("ColumnMetadata", [])]
    records = []
    for row in results.get("Records", []):
        # Each row: list of field dicts, convert to native types where possible
        parsed_row = {}
        for idx, cell in enumerate(row):
            col_name = column_info[idx] if idx < len(column_info) else f"col_{idx}"
            # cell is like {"stringValue": "..."} or {"longValue": 123} etc.
            if "stringValue" in cell:
                parsed_row[col_name] = cell["stringValue"]
            elif "blobValue" in cell:
                parsed_row[col_name] = cell["blobValue"]
            elif "doubleValue" in cell:
                parsed_row[col_name] = cell["doubleValue"]
            elif "longValue" in cell:
                parsed_row[col_name] = cell["longValue"]
            elif "booleanValue" in cell:
                parsed_row[col_name] = cell["booleanValue"]
            elif "isNull" in cell and cell["isNull"]:
                parsed_row[col_name] = None
            else:
                # unknown form; store raw
                parsed_row[col_name] = list(cell.values())[0] if cell else None
        records.append(parsed_row)

    return {"status": "finished", "rows": records, "statement_id": stmt_id}

# Set this to your transcripts table in Redshift
TRANSCRIPT_TABLE = "public.voice_to_crm" 
TRANSCRIPTION_BUCKET = "sales-copilot-bucket"
RESULT_BUCKET = "sales-copilot-bucket"
CSV_BUCKET="sales-copilot-bucket"

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


# Define the agent
def create_call_structure_agent():

    return Agent(
    name="Sales Call Analyzer",
    system_prompt="""
You are Sales Call Analyzer, an elite sales-call intelligence system specializing in turning raw conversation transcripts into structured, actionable insights.

Your responsibilities:

1. ALWAYS load the transcription data first
   - When a user asks to analyze a call or provides an HCP ID  you MUST begin by calling:
     `load_transcription_data_from_redshift(hcp_id=...)`
   - Use the returned JSON row data as the source of truth. Extract `transcript_text` as the primary transcript for analysis.
   - Incorporate contextual details from other fields (e.g., `territory_id`, `call_id`, `call_datetime_local`, `call_duration_minutes`, `structured_call_summary`, `key_topics_tags`, `objection_categories`, `compliance_redaction_flag`) to enrich your analysis and ensure relevance to the HCP's territory, history, and compliance needs.
   - Respect `compliance_redaction_flag`: If flagged, avoid referencing redacted content in outputs and note any limitations in the summary.

2. Extract structured insights
   After receiving the HCP row JSON, parse it and analyze the `transcript_text` (enhancing with other row fields where relevant). Produce a JSON object with the following fields:

   {
     "hcp_id": "the provided HCP ID",
     "territory_id": "from row data",
     "call_id": "from row data",
     "call_datetime_local": "from row data",
     "call_duration_minutes": "from row data",
     "topics_discussed": ["pricing", "integration", "timeline"],
     "objections": [
       {"objection": "Too expensive", "response": "We can offer a discount", "category": "from objection_categories if matching"}
     ],
     "commitments": [
       {"who": "Rep", "commitment": "Send proposal", "due_date": "2025-04-05"}
     ],
     "follow_ups": [
       {"action": "Schedule demo", "owner": "Rep", "due_date": "next week"}
     ],
     "summary": "The customer showed strong interest... (tailored to HCP context, improving on structured_call_summary if present)",
     "key_topics_tags": "from row data (append or refine based on analysis)",
     "objection_categories": "from row data (update with new insights)",
     "compliance_notes": "Any compliance/redaction observations from analysis"
   }

   - If a field cannot be determined, use an empty list [] or null as appropriate. For summary, make it concise yet comprehensive (200-400 words), focusing on HCP-specific insights like engagement level, pain points tied to territory, and opportunities.
   - Be concise, factual, and base all insights strictly on the transcript text, augmented by row context.

3. Saving structured notes
   - If the user explicitly asks you to SAVE the structured JSON, call:
     `save_structured_note(call_id=..., structured_json=...)`
   - Use the `call_id` from the row data. The tool payload must be the exact JSON object produced.

4. Output rules
   - When returning analysis results to the user, OUTPUT ONLY valid JSON (no commentary, no markdown).
   - When invoking a tool, return only the tool invocation according to your agent/tool protocol.
   - Do not invent or hallucinate content—only extract and contextualize what is present.

5. Behavior & quality
   - Identify commitments, objections, next steps, pain points, and key themes, even when subtle. Cross-reference with `key_topics_tags` and `objection_categories` for accuracy.
   - When interpreting phrases like "next week" or "by Friday", infer reasonable absolute due dates only if asked; otherwise keep the original phrasing and optionally provide an inferred date as a separate field.
   - Provide speaker attribution when possible (e.g., "Rep" vs "HCP") inside commitments/follow_ups/objections.
   - Tailor insights to HCP context: E.g., reference territory-specific trends if inferable from row data.

Workflow (strict):
1. Call load_transcription_data_from_redshift(hcp_id=...)
2. Parse the returned JSON row, extract and analyze transcript_text with contextual fields
3. Return the enriched structured JSON

Remember: Valid JSON only. No additional text.
""",
    tools=[load_transcription_data_from_redshift]
)

agent=create_call_structure_agent()

# ---------------------------------------------------
#  Main Runner
# ---------------------------------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}):
    # Example instruction: in real usage you can embed call_id / structured note JSON here.
    payload = payload.get("prompt","Provide structure called summary of my last call")
    agent_result = agent(payload)#type:ignore
    return agent_result

# ---------------------------------------------------
# Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()
    #run_main_agent()
