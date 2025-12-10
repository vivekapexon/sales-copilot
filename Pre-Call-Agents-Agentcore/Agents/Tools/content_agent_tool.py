import re
import os
import boto3
import pandas as pd
import io
from typing import List, Any, Dict, Union
from strands import  tool

# --- Helpers ---

def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store. Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3 bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm", region_name="us-east-1")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None


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
