from __future__ import annotations
from strands import Agent,tool
from typing import Optional, Dict, Any
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

# Config values (change anytime)
AUDIO_BUCKET = "sales-copilot-bucket"
AUDIO_PREFIX = "hcpaudiocalls/"  # <-- your audio folder prefix
TEMP_UPLOAD_BUCKET = "sales-copilot-bucket"
TRANSCRIBE_OUTPUT_BUCKET = "sales-copilot-bucket"

app = BedrockAgentCoreApp()

@tool
def transcribe_audio(
    *,
    hcp_id: Optional[str] = None,
    s3_audio_uri: Optional[str] = None,
    local_audio_path: Optional[str] = None,
    output_s3_prefix: Optional[str],
    language_code: str = "en-US",
    use_medical: bool = False, 
    media_format: Optional[str] = "mp3",
    timeout_minutes: int = 20,
    cleanup_temp: bool = False,
    enable_speaker_diarization: bool = False,
    max_speakers: int = 2,
) -> Dict[str, Any]:
    """
    Main transcription tool. Auto-builds S3 URI using only the HCP_ID and AUDIO_PREFIX.
    """
    print(f"[INFO] Starting transcription | bucket={AUDIO_BUCKET}")

    if not (hcp_id or s3_audio_uri or local_audio_path):
        raise ValueError("Provide either hcp_id, s3_audio_uri, or local_audio_path")

    s3_client = boto3.client("s3", region_name='us-east-1')
    transcribe_client = boto3.client("transcribe", region_name='us-east-1')

    # Build S3 URI automatically if hcp_id is provided
    if hcp_id and not s3_audio_uri:
        s3_audio_uri = f"s3://{AUDIO_BUCKET}/{AUDIO_PREFIX}{hcp_id}.{media_format}"
        print(f"[AUTO] Resolved s3_audio_uri = {s3_audio_uri}")

    temp_key = None
    if local_audio_path:
        if not os.path.exists(local_audio_path):
            raise FileNotFoundError(local_audio_path)
        filename = os.path.basename(local_audio_path)
        temp_key = f"tmp/transcribe/{uuid.uuid4().hex}/{filename}"
        print(f"[UPLOAD] Uploading local file to s3://{TEMP_UPLOAD_BUCKET}/{temp_key}")
        s3_client.upload_file(local_audio_path, TEMP_UPLOAD_BUCKET, temp_key)
        s3_audio_uri = f"s3://{TEMP_UPLOAD_BUCKET}/{temp_key}"

    if not media_format:
        ext = os.path.splitext(s3_audio_uri)[1].lstrip(".").lower()#type:ignore
        if ext:
            media_format = ext
        else:
            raise ValueError("media_format missing & cannot be inferred.")

    supported_formats = {"mp3", "wav", "mp4", "flac", "amr", "ogg", "webm", "m4a"}
    if media_format.lower() not in supported_formats:#type:ignore
        raise ValueError(f"Unsupported media format: {media_format}")

    job_name = f"transcribe-{uuid.uuid4().hex[:12]}"
    if not output_s3_prefix or not output_s3_prefix.startswith("s3://"):
        output_s3_prefix = f"s3://{TEMP_UPLOAD_BUCKET}/{job_name}/"

    output_bucket, output_prefix = _split_s3_prefix(output_s3_prefix)

    media_settings = {
        "MediaFormat": media_format,
        "Media": {"MediaFileUri": s3_audio_uri},
    }

    # -------------------------------
    # STANDARD TRANSCRIBE (no medical)
    # -------------------------------
    params = {
        "TranscriptionJobName": job_name,
        "LanguageCode": language_code,
        **media_settings,
        "OutputBucketName": TRANSCRIBE_OUTPUT_BUCKET,
    }

    if enable_speaker_diarization:
        params["Settings"] = {
            "ShowSpeakerLabels": True,
            "MaxSpeakerLabels": max(2, max_speakers),
        }

    transcribe_client.start_transcription_job(**params)
    get_status = lambda: transcribe_client.get_transcription_job(
        TranscriptionJobName=job_name
    )
    extract_path = ("TranscriptionJob", "Transcript", "TranscriptFileUri")
    status_path = ("TranscriptionJob", "TranscriptionJobStatus")

    # -------------------------------
    # Poll until done
    # -------------------------------
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60
    attempt = 0
    transcript_uri = None

    while True:
        if time.time() - start_time > timeout_seconds:
            raise TimeoutError("Transcription job timed out.")

        status_response = get_status()
        job_status = _deep_get(status_response, status_path)

        if job_status == "FAILED":
            fail_reason = _deep_get(status_response, (*status_path[:-1], "FailureReason"))
            raise RuntimeError(f"Transcribe job failed: {fail_reason}")

        if job_status == "COMPLETED":
            transcript_uri = _deep_get(status_response, extract_path)
            break

        time.sleep(min(60, 2 ** attempt) * random.uniform(0.5, 1.5))
        attempt += 1

    raw_json = _download_transcript(transcript_uri, s3_client)#type:ignore
    structured = _structure_transcript(raw_json)

    final_uri = f"{output_s3_prefix.rstrip('/')}/{job_name}-structured.json"

    if cleanup_temp and temp_key:
        try:
            s3_client.delete_object(Bucket=TEMP_UPLOAD_BUCKET, Key=temp_key)
        except Exception:
            print("[WARN] temp cleanup failed.")

    return {
        "transcript_s3_uri": final_uri,
        "transcript_json": structured,
        "raw_transcribe_response": raw_json,
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