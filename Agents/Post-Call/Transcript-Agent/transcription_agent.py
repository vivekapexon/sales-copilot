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

app = BedrockAgentCoreApp()

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
    """
    Transcribes audio and returns ONLY the final text transcription.
    Raw and structured transcripts are persisted to S3 internally.
    """

    if not (hcp_id or s3_audio_uri or local_audio_path):
        raise ValueError("Provide either hcp_id, s3_audio_uri, or local_audio_path")

    s3_client = boto3.client("s3", region_name="us-east-1")
    transcribe_client = boto3.client("transcribe", region_name="us-east-1")

    # Build S3 URI from HCP ID
    if hcp_id and not s3_audio_uri:
        s3_audio_uri = f"s3://{AUDIO_BUCKET}/{AUDIO_PREFIX}{hcp_id}.{media_format}"

    # Upload local file if provided
    temp_key = None
    if local_audio_path:
        if not os.path.exists(local_audio_path):
            raise FileNotFoundError(local_audio_path)
        filename = os.path.basename(local_audio_path)
        temp_key = f"tmp/transcribe/{uuid.uuid4().hex}/{filename}"
        s3_client.upload_file(local_audio_path, TEMP_UPLOAD_BUCKET, temp_key)
        s3_audio_uri = f"s3://{TEMP_UPLOAD_BUCKET}/{temp_key}"

    # Infer media format if missing
    if not media_format:
        ext = os.path.splitext(s3_audio_uri)[1].lstrip(".").lower()  # type: ignore
        if not ext:
            raise ValueError("media_format missing & cannot be inferred")
        media_format = ext

    supported_formats = {
        "mp3", "wav", "mp4", "flac", "amr", "ogg", "webm", "m4a"
    }
    if media_format.lower() not in supported_formats:
        raise ValueError(f"Unsupported media format: {media_format}")

    job_name = f"transcribe-{uuid.uuid4().hex[:12]}"

    if not output_s3_prefix or not output_s3_prefix.startswith("s3://"):
        output_s3_prefix = f"s3://{TEMP_UPLOAD_BUCKET}/transcripts/{job_name}/"

    output_bucket, output_prefix = _split_s3_prefix(output_s3_prefix)

    # Start Transcription Job
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

    transcribe_client.start_transcription_job(**params)

    # Poll until complete
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    attempt = 0

    while True:
        if time.time() - start_time > timeout_seconds:
            raise TimeoutError("Transcription job timed out")

        response = transcribe_client.get_transcription_job(
            TranscriptionJobName=job_name
        )

        status = _deep_get(
            response,
            ("TranscriptionJob", "TranscriptionJobStatus"),
        )

        if status == "FAILED":
            reason = _deep_get(
                response,
                ("TranscriptionJob", "FailureReason"),
            )
            raise RuntimeError(f"Transcription failed: {reason}")

        if status == "COMPLETED":
            transcript_uri = _deep_get(
                response,
                ("TranscriptionJob", "Transcript", "TranscriptFileUri"),
            )
            break

        time.sleep(min(60, 2 ** attempt) * random.uniform(0.5, 1.5))
        attempt += 1

    # ---------------------------------------------------
    # Download ONCE, persist internally, return text only
    # ---------------------------------------------------
    raw_json = _download_transcript(transcript_uri, s3_client)  # type: ignore

    # Persist RAW
    raw_key = f"{output_prefix.rstrip('/')}/{job_name}-raw.json"
    s3_client.put_object(
        Bucket=output_bucket,
        Key=raw_key,
        Body=json.dumps(raw_json).encode("utf-8"),
        ContentType="application/json",
    )

    structured = _structure_transcript(raw_json)

    # Persist structured
    structured_key = f"{output_prefix.rstrip('/')}/{job_name}-structured.json"
    s3_client.put_object(
        Bucket=output_bucket,
        Key=structured_key,
        Body=json.dumps(structured, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    if cleanup_temp and temp_key:
        try:
            s3_client.delete_object(
                Bucket=TEMP_UPLOAD_BUCKET,
                Key=temp_key,
            )
        except Exception:
            pass

    return {
        "text": structured["text"]
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
    from urllib.parse import urlparse
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        obj = s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))

    import urllib.request
    with urllib.request.urlopen(uri) as r:
        return json.loads(r.read().decode("utf-8"))


def _structure_transcript(transcript_json: dict) -> dict:
    results = transcript_json.get("results", {})
    transcripts = results.get("transcripts", [])
    items = results.get("items", [])

    if transcripts:
        full_text = " ".join(t.get("transcript", "") for t in transcripts).strip()
    else:
        words = []
        for it in items:
            if it.get("type") == "punctuation" and words:
                words[-1] += it["alternatives"][0]["content"]
            else:
                words.append(it["alternatives"][0]["content"])
        full_text = " ".join(words).strip()

    return {
        "jobName": transcript_json.get("jobName", ""),
        "text": full_text,
        "results": {
            "transcripts": transcripts,
            "items": items
        }
    }


def _deep_get(dct: dict, path: tuple[str, ...]):
    cur = dct
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur

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