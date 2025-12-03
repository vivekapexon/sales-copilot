import re
import os
import boto3
import pandas as pd
import io
from typing import List, Any, Dict
from strands import  tool

# --- Helpers ---
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
def read_personalized_csv(url: str = "", csv_content_limit: int = 10) -> List[Dict[str, Any]]:
    """
    Load a CSV file from an S3 URL.
    with the application.

    Use this tool when the user wants to load HCP/CRM data, records, or any other
    structured dataset that is stored in CSV format. The tool supports below data
    sources in order of priority:
        1. An S3 URL (starting with s3://)
 

    Parameters:
        url: A string representing either:
            - An S3 URL of the form "s3://bucket-name/path/to/file.csv"
        csv_content_limit: A integer representing limit of csv data to be passed to llm.

    Behavior:
        - If `url` is an S3 URL:
            * Validates AWS credentials via STS.
            * Reads the CSV from S3.

    Returns:
        A list of dictionaries, where each dictionary corresponds to a row in
        the CSV, with all values coerced to strings and missing values replaced
        with empty strings.

    Raises:
        RuntimeError: If AWS credentials are missing/invalid or if an S3 read error occurs.
        FileNotFoundError: If the file cannot be located in S3
    """

    # --- 1. Load from S3 ---
    if _is_s3_url(url):
        print(f"Using S3 for csv file: {url}")
        without_prefix = url[len("s3://"):]
        bucket, key = without_prefix.split("/", 1)

        try:
            s3 = boto3.client("s3",region_name='us-east-1')
            obj = s3.get_object(Bucket=bucket, Key=key)

            raw_bytes = obj["Body"].read()  # read correct buffer
            df = pd.read_csv(io.BytesIO(raw_bytes), dtype=str)[:csv_content_limit]
            df = df.fillna("")

            return df.to_dict(orient="records")  # type: ignore

        except s3.exceptions.NoSuchKey:
            raise FileNotFoundError(f"S3 key not found: s3://{bucket}/{key}")
        except s3.exceptions.NoSuchBucket:
            raise FileNotFoundError(f"S3 bucket not found: {bucket}")
        except Exception as e:
            raise RuntimeError(f"Error reading S3 CSV: {e}")

    # --- 4. Nothing found ---
    raise FileNotFoundError(
        f"No CSV found Provide an S3 URL."
    )

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
