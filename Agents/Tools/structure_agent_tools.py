#structure agent.py
import json
import boto3
import os
from typing import Dict, Any
from strands import tool
import pandas as pd
# AWS clients 
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name= "us-east-1")

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
def load_hcp_data_from_s3(hcp_id: str) -> str:
    """
    Load a CSV file from Amazon S3 bucket and return the data row for the specified HCP ID as JSON string.
    
    Args:
        hcp_id: The HCP ID to filter and retrieve the specific row for.
    
    Returns:
        The row data as a JSON string, or an error message if not found.
    """

    print(f"Loading CSV from s3://{CSV_BUCKET}/{S3_DEMO_TRASNCRPTION_JSON_FILE} and filtering for HCP ID: {hcp_id}")

    try:
        obj = s3.get_object(Bucket=CSV_BUCKET, Key=S3_DEMO_TRASNCRPTION_JSON_FILE)
        df = pd.read_csv(obj["Body"])
        
        row = df[df['hcp_id'] == hcp_id]
        
        if row.empty:
            return json.dumps({"error": f"No row found for HCP ID: {hcp_id}"})
        row_data = row.iloc[0].to_dict()
        return json.dumps(row_data)

    except Exception as e:
        print(f"Error loading or processing CSV: {str(e)}")
        return json.dumps({"error": f"Failed to load data: {str(e)}"})
    