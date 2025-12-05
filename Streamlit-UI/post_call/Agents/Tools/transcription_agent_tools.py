from __future__ import annotations
import os
import json
import time
import uuid
import random
from typing import Optional, Dict, Any

import boto3
from strands import  tool

temp_upload_bucket ="sales-copilot-bucket"
transcribe_output_bucket = "sales-copilot-bucket"
@tool
def transcribe_audio(
                *,
                s3_audio_uri: Optional[str] = None,
                local_audio_path: Optional[str] = None,
                output_s3_prefix: str,
                language_code: str = "en-US",
                use_medical: bool = True,
                media_format: Optional[str] = None,
                timeout_minutes: int = 20,
                cleanup_temp: bool = False,
                enable_speaker_diarization: bool = False,
                max_speakers: int = 2,
            ) -> Dict[str, Any]:
    """
    Start an Amazon Transcribe job, poll until completion, download + normalize transcript,
    write structured JSON to `output_s3_prefix`, and return a dict:
      {
        "transcript_s3_uri": "s3://bucket/key",
        "transcript_json": { ... normalized structure ... },
        "raw_transcribe_response": {...}
      }
    """

    print(f"In AWS region: , using temp upload bucket: {temp_upload_bucket}, transcribe output bucket: {transcribe_output_bucket}")

    if not (s3_audio_uri or local_audio_path):
        raise ValueError("Provide either s3_audio_uri or local_audio_path")
    if use_medical and not transcribe_output_bucket:
        raise ValueError("TRANSCRIBE_OUTPUT_BUCKET required for medical transcription")

    s3_client = boto3.client("s3", region_name='us-east-1')
    transcribe_client = boto3.client("transcribe", region_name='us-east-1')

    temp_key = None
    try:
        # Upload local file if necessary
        if local_audio_path:
            if not temp_upload_bucket:
                raise EnvironmentError("TEMP_UPLOAD_BUCKET must be set when using local_audio_path")
            if not os.path.exists(local_audio_path):
                raise FileNotFoundError(local_audio_path)
            filename = os.path.basename(local_audio_path)
            temp_key = f"tmp/transcribe/{uuid.uuid4().hex}/{filename}"
            print(f"Uploading local audio file to s3://{temp_upload_bucket}/{temp_key}")
            try:
                s3_client.upload_file(local_audio_path, temp_upload_bucket, temp_key)
            except Exception as e:
                print(f"Failed to upload local audio file: {e}")
                raise
            media_uri = f"s3://{temp_upload_bucket}/{temp_key}"
        else:
            media_uri = s3_audio_uri  # type: ignore

        # Infer media_format if not provided
        if not media_format:
            import os as _os
            parsed = media_uri
            if isinstance(media_uri, str) and "/" in media_uri:
                ext = _os.path.splitext(media_uri)[1].lstrip(".").lower()
                if ext:
                    media_format = ext
        if not media_format:
            raise ValueError("media_format could not be inferred; provide media_format explicitly")

        supported = {"mp3", "mp4", "wav", "flac", "amr", "ogg", "webm"}
        if media_format.lower() not in supported:
            raise ValueError(f"Unsupported media format {media_format}")

        if not output_s3_prefix.startswith("s3://"):
            raise ValueError("output_s3_prefix must be s3://bucket/prefix/")

        job_name = f"transcribe-{uuid.uuid4().hex[:12]}"
        output_bucket, output_prefix = _split_s3_prefix(output_s3_prefix)

        # Build params & start
        common = {"MediaFormat": media_format, "Media": {"MediaFileUri": media_uri}}
        if use_medical:
            params = {"MedicalTranscriptionJobName": job_name, "LanguageCode": language_code, **common}
            if transcribe_output_bucket:
                params["OutputBucketName"] = transcribe_output_bucket
            transcribe_client.start_medical_transcription_job(**params)
            get_status = lambda: transcribe_client.get_medical_transcription_job(MedicalTranscriptionJobName=job_name)
            extract_uri_path = ("MedicalTranscriptionJob", "Transcript", "TranscriptFileUri")
            status_path = ("MedicalTranscriptionJob", "TranscriptionJobStatus")
        else:
            params = {"TranscriptionJobName": job_name, "LanguageCode": language_code, **common}
            if enable_speaker_diarization:
                params.setdefault("Settings", {})
                params["Settings"]["ShowSpeakerLabels"] = True
                params["Settings"]["MaxSpeakerLabels"] = max(2, max_speakers)
            if transcribe_output_bucket:
                params["OutputBucketName"] = transcribe_output_bucket
            transcribe_client.start_transcription_job(**params)
            get_status = lambda: transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            extract_uri_path = ("TranscriptionJob", "Transcript", "TranscriptFileUri")
            status_path = ("TranscriptionJob", "TranscriptionJobStatus")

        # Poll
        timeout_seconds = timeout_minutes * 60
        start = time.time()
        attempt = 0
        transcript_uri = None
        while True:
            if time.time() - start > timeout_seconds:
                raise TimeoutError("Transcription timed out")
            status_resp = get_status()
            job_status = _deep_get(status_resp, status_path)
            if job_status == "FAILED":
                reason = _deep_get(status_resp, (*status_path[:-1], "FailureReason")) or "Unknown"
                raise RuntimeError(f"Transcribe job failed: {reason}")
            if job_status == "COMPLETED":
                transcript_uri = _deep_get(status_resp, extract_uri_path)
                break
            sleep_base = min(60, 2 ** attempt)
            time.sleep(sleep_base * random.uniform(0.5, 1.5))
            attempt += 1

        if not transcript_uri:
            raise RuntimeError("No transcript URI after completion")

        raw_json = _download_transcript(transcript_uri, s3_client=s3_client)#type:ignore
        structured = _structure_transcript(raw_json)

        # upload structured JSON to output prefix
        out_key = f"{output_prefix.rstrip('/')}/{job_name}-structured.json" if output_prefix else f"{job_name}-structured.json"
        s3_client.put_object(Bucket=output_bucket, Key=out_key, Body=json.dumps(structured, indent=2), ContentType="application/json")
        transcript_s3_uri = f"s3://{output_bucket}/{out_key}"

        if cleanup_temp and temp_key:
            try:
                s3_client.delete_object(Bucket=temp_upload_bucket, Key=temp_key)
            except Exception:
                print("temp cleanup failed")

        return {"transcript_s3_uri": transcript_s3_uri, "transcript_json": structured, "raw_transcribe_response": raw_json}
    finally:
        # if you want strict cleanup on exception: implement here (kept simple)
        pass


def _split_s3_prefix(p: str) -> tuple[str, str]:
    assert p.startswith("s3://")
    body = p[5:]
    parts = body.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


def _download_transcript(uri: str, s3_client=None) -> dict:
    from urllib.parse import urlparse
    if not s3_client:
        raise RuntimeError("s3_client required")
    parsed = urlparse(uri)
    if parsed.scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        resp = s3_client.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    import urllib.request
    with urllib.request.urlopen(uri) as r:
        return json.loads(r.read().decode("utf-8"))


def _structure_transcript(transcript_json: dict) -> dict:
    results = transcript_json.get("results", {})
    items = results.get("items", [])
    transcripts = results.get("transcripts", [])
    if transcripts:
        full_text = " ".join(t.get("transcript", "") for t in transcripts).strip()
    else:
        words = []
        for it in items:
            if it.get("type") == "punctuation" and words:
                words[-1] += it.get("alternatives", [{}])[0].get("content", "")
            else:
                words.append(it.get("alternatives", [{}])[0].get("content", ""))
        full_text = " ".join(words).strip()
    structured = {"jobName": transcript_json.get("jobName", ""), "text": full_text, "results": {"transcripts": transcripts, "items": items}}
    if not items and full_text:
        words = full_text.split()
        if words:
            step = max(0.1, len(words) * 0.5 / len(words))
            structured["results"]["items"] = [{"start_time": f"{i*step:.3f}", "end_time": f"{(i+1)*step:.3f}", "alternatives": [{"content": w, "confidence": "1.0"}], "type": "pronunciation"} for i, w in enumerate(words)]
    return structured


def _deep_get(dct: dict, path: tuple[str, ...]):
    cur = dct
    for p in path:
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return None
    return cur
