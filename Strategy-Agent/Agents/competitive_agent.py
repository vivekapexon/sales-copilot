# competitive_agent.py


import os
import io
import json
import math
import zipfile
import logging
from typing import Any, Dict, List, Tuple

import boto3
import pandas as pd
import numpy as np
from strands import Agent, tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("competitive_agent")

# ============================================================
# GLOBAL SIGNAL STORAGE
# ============================================================
GLOBAL_SIGNALS: List[Dict[str, Any]] = []


# ============================================================
# UTILITIES
# ============================================================
def prepare_numeric_matrix(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Auto-detect numeric columns, coerce to numeric, remove constant columns.
    Returns numeric_df and list of numeric column names.
    """
    numeric_cols: List[str] = []
    numeric_df = pd.DataFrame(index=df.index)

    for col in df.columns:
        coerced = pd.to_numeric(df[col], errors="coerce")
        if coerced.notna().sum() == 0:
            continue
        if coerced.dropna().nunique() <= 1:
            continue
        numeric_df[col] = coerced.astype(float)
        numeric_cols.append(col)

    return numeric_df, numeric_cols


# ============================================================
# TOOL 1 — UNIVERSAL S3 LOADER
# ============================================================
@tool
def fetch_competitive_data_s3(bucket: str, key: str) -> Dict[str, Any]:
    """
    Load file from S3. Supports CSV, TSV, XLSX, JSON, PARQUET, ZIP.
    Returns: {status, rows, source, ref}
    """
    s3 = boto3.client("s3")
    ref = f"s3://{bucket}/{key}"

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read()
    except Exception as e:
        return {"status": "error", "error": str(e)}

    lower = key.lower()

    try:
        if lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(body))
        elif lower.endswith(".tsv"):
            df = pd.read_csv(io.BytesIO(body), sep="\t")
        elif lower.endswith(".json"):
            try:
                df = pd.read_json(io.BytesIO(body), orient="records")
            except:
                df = pd.read_json(io.BytesIO(body), lines=True)
        elif lower.endswith((".xls", ".xlsx")):
            df = pd.read_excel(io.BytesIO(body))
        elif lower.endswith(".parquet"):
            df = pd.read_parquet(io.BytesIO(body))
        elif lower.endswith(".zip"):
            z = zipfile.ZipFile(io.BytesIO(body))
            inner_name = None
            for n in z.namelist():
                if n.lower().endswith((".csv", ".tsv", ".json", ".xls", ".xlsx", ".parquet")):
                    inner_name = n
                    break
            if inner_name is None:
                return {"status": "error", "error": "Unsupported file inside ZIP"}
            content = z.read(inner_name)
            lname = inner_name.lower()
            if lname.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content))
            elif lname.endswith(".tsv"):
                df = pd.read_csv(io.BytesIO(content), sep="\t")
            elif lname.endswith(".json"):
                try:
                    df = pd.read_json(io.BytesIO(content), orient="records")
                except:
                    df = pd.read_json(io.BytesIO(content), lines=True)
            elif lname.endswith((".xls", ".xlsx")):
                df = pd.read_excel(io.BytesIO(content))
            elif lname.endswith(".parquet"):
                df = pd.read_parquet(io.BytesIO(content))
        else:
            return {"status": "error", "error": f"Unsupported file type: {key}"}

    except Exception as e:
        return {"status": "error", "error": f"File parse failed: {str(e)}"}

    rows = df.to_dict(orient="records")
    return {"status": "ok", "rows": rows, "source": "s3", "ref": ref}


# ============================================================
# TOOL 2 — GENERIC SIGNAL ENGINE 
# ============================================================
@tool
def compute_signals_generic(rows: List[Dict[str, Any]], source: str, ref: str) -> List[Dict[str, Any]]:
    df = pd.DataFrame(rows)
    if df.empty:
        return []

    numeric_df, numeric_cols = prepare_numeric_matrix(df)

    # If no numeric columns → error per row
    if not numeric_cols:
        signals = []
        for idx, row in df.iterrows():
            signals.append({
                "hcp_id": row.get("hcp_id"),
                "hco_id": row.get("hco_id"),
                "territory_id": row.get("territory_id"),
                "drug_id": row.get("drug_id"),
                "signal_score": None,
                "signal_severity": None,
                "numeric_metrics": {},
                "citation": {"ref": ref, "row_index": int(idx)},
                "error": "No numeric fields available"
            })
        return signals

    # Normalize numeric matrix
    mins = numeric_df.min()
    maxs = numeric_df.max()
    ranges = (maxs - mins).replace(0, 1)

    normalized = (numeric_df - mins) / ranges
    normalized = normalized.fillna(0.0)

    # Score = mean of normalized numeric cols
    row_scores = normalized.mean(axis=1)

    # Severity thresholds (percentiles)
    p33 = float(np.percentile(row_scores, 33))
    p66 = float(np.percentile(row_scores, 66))

    def severity(s: float) -> str:
        if s >= p66:
            return "High"
        elif s >= p33:
            return "Medium"
        return "Low"

    signals = []

    # MAIN LOOP — with price-gap fix
    for idx, row in df.iterrows():
        idx_i = int(idx)

        # ---- PRICE GAP FIX (CAP TO ±100%) ----
        if "price_gap_vs_competitor_percent" in numeric_cols:
            raw_val = row.get("price_gap_vs_competitor_percent")
            if raw_val is not None and not pd.isna(raw_val):
                if abs(raw_val) > 100:
                    row["price_gap_vs_competitor_percent"] = 100 if raw_val > 0 else -100

        score = float(row_scores[idx_i])
        sev = severity(score)

        # Build numeric_metrics using updated row values
        numeric_metrics = {
            col: None if pd.isna(row[col]) else row[col]
            for col in numeric_cols
        }

        signals.append({
            "hcp_id": row.get("hcp_id"),
            "hco_id": row.get("hco_id"),
            "territory_id": row.get("territory_id"),
            "drug_id": row.get("drug_id"),
            "drug_name": row.get("drug_name"),
            "signal_score": round(score, 3),
            "signal_severity": sev,
            "numeric_metrics": numeric_metrics,
            "citation": {"ref": ref, "row_index": idx_i}
        })

    return signals



# ============================================================
# TOOL 3 — Query Signals (ONLY interface the agent may use)
# ============================================================
@tool
def query_signals(question: str) -> Dict[str, Any]:
    """
    LLM retrieves stored signals always from GLOBAL_SIGNALS.
    """
    return {
        "status": "ok",
        "question": question,
        "signals": GLOBAL_SIGNALS
    }



SYSTEM_PROMPT = """
You are the Competitive Intelligence Agent.

STRICT RULES (DO NOT BREAK):
- You MUST use only the query_signals tool to access dataset information.
- You MUST NOT add, invent, assume, or generate ANY new KPI, field, category, structure, or value.
- You MUST NOT create nested structures such as “clinical_priorities”, “market_position”, “risk_assessment”, “performance_metrics”, or ANY grouping.
- You MUST NOT output categories or summaries unless they ALREADY exist in GLOBAL_SIGNALS.
- You MUST use ONLY the keys that appear exactly in GLOBAL_SIGNALS.
- If a value or key does not exist in GLOBAL_SIGNALS, you MUST NOT create it.
- If user asks for something not directly available in GLOBAL_SIGNALS, respond with:
  {"error": "Not available in dataset"}.
- NEVER hallucinate or generate synthetic, assumed, estimated, or invented values.
- NEVER restructure the data except for filtering or selecting existing keys.

MANDATORY OUTPUT STRUCTURE:
You MUST always return a dictionary with the following structure:

{
  "json": { ... },
  "text": "human readable explanation"
}

JSON BLOCK RULES:
- Use EXACT keys from GLOBAL_SIGNALS (no additional fields).
- Use snake_case keys only.
- NO nested objects unless the dataset contains nested objects (your dataset does not).
- You MUST include the citation object exactly as it appears in GLOBAL_SIGNALS:
  "citation": {"ref": "...", "row_index": ...}
- NO grouping, NO categories, NO hierarchy.
- The JSON MUST BE FLAT.

TEXT BLOCK RULES:
- You may describe insights or patterns in natural language.
- You MUST base ALL narrative ONLY on values present in GLOBAL_SIGNALS.
- You MUST NOT invent insights, KPIs, or clinical categories.
- If the needed fields are not present, explicitly say so.

ALLOWED ACTIONS:
- Filter rows.
- Sort rows.
- Extract existing fields.
- Compare values that exist.
- Describe what is in the dataset.

NOT ALLOWED:
- KPI calculation.
- KPI formulas.
- Clinical interpretation outside numeric values.
- Adding fields.
- Summaries based on missing or external data.
- Nested JSON.
- Any hallucination of missing numbers.

YOU ARE THE COMPETITIVE INTELLIGENCE AGENT.

"""


# ============================================================
# AGENT FACTORY
# ============================================================
def create_competitive_agent() -> Agent:
    return Agent(
        system_prompt=SYSTEM_PROMPT,
        tools=[fetch_competitive_data_s3, compute_signals_generic, query_signals]
    )


# ============================================================
# SETUP — Load data from S3 once
# ============================================================
def run_competitive_setup_s3(bucket: str, key: str) -> Dict[str, Any]:
    global GLOBAL_SIGNALS
    GLOBAL_SIGNALS = []

    fetch = fetch_competitive_data_s3(bucket=bucket, key=key)
    if fetch.get("status") != "ok":
        return fetch

    rows = fetch["rows"]
    ref = fetch["ref"]
    source = fetch["source"]

    GLOBAL_SIGNALS = compute_signals_generic(rows, source, ref)
    return {
        "status": "ok",
        "loaded_rows": len(rows),
        "computed_signals": len(GLOBAL_SIGNALS),
        "source": ref
    }


# ============================================================
# MAIN — Strand auto prints, no print() needed
# ============================================================
if __name__ == "__main__":
    BUCKET = os.environ.get("COMP_BUCKET", "competitive-data-bucket")
    # KEY = os.environ.get("COMP_KEY", "data/competitive_dataset_clean.csv")    #old data
    KEY = os.environ.get("COMP_KEY", "data/competitive_agent_final_data_set.csv")      #new data
    print("Loading from S3...")
    
    print(run_competitive_setup_s3(BUCKET, KEY))
    agent = create_competitive_agent()

    # Strand will AUTO-PRINT the response. No print() needed.
    agent("Show me the highest severity HCP signals.")
    # agent("Explain the signal reasoning for row 10.")
    # agent("List HCPs with medium severity signals.")
   
