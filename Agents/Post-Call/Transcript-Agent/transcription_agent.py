from __future__ import annotations
from strands import Agent, tool
from typing import Optional, Dict, Any, Tuple
import os
import json
import time
import uuid
import random
import boto3
import logging
from urllib.parse import urlparse
from bedrock_agentcore.runtime import BedrockAgentCoreApp
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("transciption_agent")


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
    
# Config values (change anytime)
AUDIO_BUCKET = get_parameter_value("SC_POC_SA_TA_BUCKET")
AUDIO_PREFIX = get_parameter_value("SC_POC_TA_AUDIO_PREFIX")
TEMP_UPLOAD_BUCKET = get_parameter_value("SC_POC_SA_TA_BUCKET")
TRANSCRIBE_OUTPUT_BUCKET = get_parameter_value("SC_POC_SA_TA_BUCKET")

WORKGROUP = get_parameter_value("REDSHIFT_WORKGROUP")
DATABASE = get_parameter_value("SC_REDSHIFT_DATABASE")
SECRET_ARN = get_parameter_value("SC_REDSHIFT_SECRET_ARN")

DEFAULT_SQL_LIMIT = 1000
SQL_POLL_INTERVAL_SECONDS = 0.5
SQL_POLL_MAX_SECONDS = 30.0

app = BedrockAgentCoreApp()

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

def _fallback_to_redshift(hcp_id: str) -> Dict[str, Any]:
    sql = f"""
        SELECT transcript_text
        FROM public.voice_to_crm
        WHERE hcp_id = '{hcp_id}'
        ORDER BY call_datetime_local DESC
        LIMIT 1
    """
    rs = execute_redshift_sql(sql)

    if rs.get("status") == "finished" and rs.get("rows"):
        text = rs["rows"][0].get("transcript_text")
        if text:
            return {
                "status": "success",
                "source": "redshift",
                "text": text,
            }

    return {
        "status": "insufficient_data",
        "reason": "no_backup_transcript",
    }


@tool
def transcribe_audio(
    *,
    hcp_id: Optional[str] = None,
    s3_audio_uri: Optional[str] = None,
    local_audio_path: Optional[str] = None,
    output_s3_prefix: Optional[str] = None,
    language_code: str = "en-US",
    media_format: Optional[str] = "mp3",
    timeout_minutes: int = 20,
    cleanup_temp: bool = False,
    enable_speaker_diarization: bool = False,
    max_speakers: int = 2,
) -> Dict[str, Any]:

    # -------------------------------
    # 1. Validate input (NO EXCEPTIONS)
    # -------------------------------
    if not (hcp_id or s3_audio_uri):
        return {
            "status": "insufficient_data",
            "reason": "missing_input",
            "required": ["hcp_id"],
        }

    if hcp_id and not s3_audio_uri:
        s3_audio_uri = f"s3://{AUDIO_BUCKET}/{AUDIO_PREFIX}{hcp_id}.{media_format}"

    supported_formats = {"mp3", "wav", "mp4", "flac", "amr", "ogg", "webm", "m4a"}
    if media_format.lower() not in supported_formats:#type:ignore
        return _fallback_to_redshift(hcp_id)#type:ignore

    s3_client = boto3.client("s3", region_name="us-east-1")
    transcribe_client = boto3.client("transcribe", region_name="us-east-1")

    job_name = f"transcribe-{uuid.uuid4().hex[:12]}"
    output_prefix = f"s3://{TEMP_UPLOAD_BUCKET}/transcripts/{job_name}/"
    output_bucket, output_key = _split_s3_prefix(output_prefix)

    logger.info(f"[DEBUG] Transcribe MediaFileUri = {s3_audio_uri}")

    params = {
        "TranscriptionJobName": job_name,
        "LanguageCode": language_code,
        "MediaFormat": media_format,
        "Media": {"MediaFileUri": s3_audio_uri},
        "OutputBucketName": TRANSCRIBE_OUTPUT_BUCKET,
    }

    if enable_speaker_diarization:
        params["Settings"] = {
            "ShowSpeakerLabels": True,
            "MaxSpeakerLabels": max(2, max_speakers),
        }

    try:
        transcribe_client.start_transcription_job(**params)
    except Exception:
        logger.warning("start_transcription_job failed, falling back", exc_info=True)
        return _fallback_to_redshift(hcp_id)#type:ignore

    start_time = time.time()
    while True:
        if time.time() - start_time > timeout_minutes * 60:
            return _fallback_to_redshift(hcp_id)#type:ignore
            
        response = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name)
        status = response["TranscriptionJob"]["TranscriptionJobStatus"]

        if status == "FAILED":
            return _fallback_to_redshift(hcp_id)#type:ignore


        if status == "COMPLETED":
            transcript_uri = response["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
            break

        time.sleep(2)

    try:
        raw_json = _download_transcript(transcript_uri, s3_client)
    except Exception:
        logger.warning("Transcript download failed, falling back", exc_info=True)
        return _fallback_to_redshift(hcp_id)#type:ignore
      

    s3_client.put_object(
        Bucket=output_bucket,
        Key=f"{output_prefix.rstrip('/')}/{job_name}-raw.json",
        Body=json.dumps(raw_json).encode("utf-8"),
        ContentType="application/json",
    )

    structured = _structure_transcript(raw_json)
    if not structured["text"]:
        return _fallback_to_redshift(hcp_id)#type:ignore
        
    s3_client.put_object(
        Bucket=output_bucket,
        Key=f"{output_prefix.rstrip('/')}/{job_name}-structured.json",
        Body=json.dumps(structured, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    # -------------------------------
    # 7. FINAL SUCCESS (CRITICAL)
    # -------------------------------
    return {
        "status": "success",
        "source": "transcribe",
        "text": structured["text"],
    }

# -------------------------------
# Helpers
# -------------------------------
def _split_s3_prefix(uri: str) -> tuple[str, str]:
    assert uri.startswith("s3://")
    without = uri[5:]
    bucket, *rest = without.split("/", 1)
    prefix = rest[0] if rest else ""
    return bucket, prefix


def _download_transcript(uri: str, s3_client):
    parsed = urlparse(uri)

    if parsed.scheme in ("http", "https"):
        path = parsed.path.lstrip("/")
        bucket, key = path.split("/", 1)
    elif parsed.scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    else:
        raise ValueError(f"Unsupported URI scheme: {parsed.scheme}")

    obj = s3_client.get_object(Bucket=bucket, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def _structure_transcript(transcript_json: dict) -> dict:
    results = transcript_json.get("results", {})
    transcripts = results.get("transcripts", [])
    text = " ".join(t["transcript"] for t in transcripts).strip()
    return {"text": text, "results": results}


TRANSCRIPTION_AGENT_SYSTEM_PROMPT = """
You are a medical-grade transcription agent specialized in HCP (healthcare professional)
and pharmaceutical sales conversations.

Your responsibilities:

1. Extract from the user's request:
   - HCP ID (e.g., "HCP1001")
   - media_format (default: mp3)
   - diarization settings if mentioned
   - any other explicit parameters provided

2. Do NOT construct S3 paths yourself.
   Instead, pass the extracted HCP ID to the transcribe_audio tool.

   The tool will automatically build the correct S3 URI:
   s3://<AUDIO_BUCKET>/<HCP_ID>.<media_format>

3. Call transcribe_audio with only valid fields per schema.
   Do not add extra fields.

4. Return ONLY the tool's raw JSON output.
   Never summarize or rewrite the transcript.

5. If required values are missing, respond with:
   {"status": "missing_parameters", "required": ["hcp_id"]}

Rules:
- Never hallucinate audio.
- Always prioritize accuracy for medical terminology.
"""

def create_transcription_agent() -> Agent:
    return Agent(
    system_prompt=TRANSCRIPTION_AGENT_SYSTEM_PROMPT,
    tools=[transcribe_audio],
)

agent=create_transcription_agent()

@app.entrypoint
def run_main_agent(payload: dict = {}):
    payload = payload.get("prompt", "Please transcribe audio for HCP1001 using medical mode..")
    agent_result = agent(payload)#type:ignore
    return agent_result

# ---------------------------------------------------
# 5) Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()