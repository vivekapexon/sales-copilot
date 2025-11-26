import json
import re
from typing import List, Any, Dict
import pandas as pd
import os
from strands import Agent, tool
import boto3
import io

from dotenv import load_dotenv
load_dotenv(".env")
# Load S3-related environment variables
url = os.environ.get("S3_CSV_URL")
aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID")
aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
aws_session_token = os.environ.get("AWS_SESSION_TOKEN")
aws_region = os.environ.get("AWS_REGION")


def tool(fn):
    return fn

class Agent:
    def __init__(self, system_prompt="", tools=None):
        self.system_prompt = system_prompt
        self.tools = tools or []

    def __call__(self, instruction, **kwargs):
        # Indicate that the real `strands` agent is not available so caller
        # falls back to the local tool-based analyzer.
        raise RuntimeError("strands.Agent not available in this environment")

# Path to CSV in workspace (computed relative to this file)
CSV_PATH = os.path.normpath(
	os.path.join(
		os.path.dirname(__file__),
		"..",
		"Pre and Post Call datasets with Metadata 1",
		"Pre-Call",
		"personalized_call_briefs.csv",
	)
)
OUTPUT_FILE = "content_agent_output.json"


@tool
def read_personalized_csv() -> pd.DataFrame:
	if url.startswith("s3://"):
		print("Fetching CSV from S3...")
		without_prefix = url[len("s3://") :]
		parts = without_prefix.split("/", 1)
		bucket, key = parts[0], parts[1]
		session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
            region_name=aws_region,
        )
		s3 = session.client("s3")
		obj = s3.get_object(Bucket=bucket, Key=key)
		body = obj["Body"].read()
		df = pd.read_csv(io.BytesIO(body))
		df = df.fillna("")
		return df.to_dict(orient="records")
	else:
		df = pd.read_csv(CSV_PATH, dtype=str)
		df = df.fillna("")
		return df.to_dict(orient="records")
	
# def read_personalized_csv() -> List[Dict[str, Any]]:
# 	"""Read the personalized_call_briefs.csv and return list of dicts (records).

# 	Returns a list of rows as dicts. Consumer tools/agent should filter by hcp_id.
# 	"""
# 	df = pd.read_csv(CSV_PATH, dtype=str)
# 	df = df.fillna("")
# 	return df.to_dict(orient="records")


def _extract_percent(text: str) -> float:
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
def analyze_hcps(records: List[Dict[str, Any]], hcp_ids: List[str]) -> List[Dict[str, Any]]:
	"""Analyze engagement fields for given HCP ids and return ranked JSON-ready list.

	Scoring heuristic (simple, explainable):
	- Opened MOA email (moa_email_summary contains 'Opened'): +1
	- Clicked KOL video flag 'Yes': +2
	- Percent watched from kol_video_summary: add (percent/100)*2
	"""
	rows = {r.get("hcp_id"): r for r in records}
	results = []
	for h in hcp_ids:
		r = rows.get(h)
		if not r:
			results.append({"hcp_id": h, "rank": None, "score": 0.0, "reason": "HCP id not found", "details": {}})
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
			# non-empty but not explicit 'Opened'
			score += 0.5
			reasons.append("MOA email interaction noted")

		if clicked:
			score += 2.0
			reasons.append("Clicked/Watched KOL video")

		pct = _extract_percent(kol_summary)
		if pct > 0:
			add = (pct / 100.0) * 2.0
			score += add
			reasons.append(f"KOL video watch {pct}%")

		# Build human-friendly reason
		reason = "; ".join(reasons) if reasons else "No clear engagement"

		results.append({
			"hcp_id": h,
			"score": round(score, 3),
			"reason": reason,
			"details": {
				"moa_email_summary": moa,
				"clicked_kol_video_flag": r.get("clicked_kol_video_flag", ""),
				"kol_video_summary": kol_summary,
			},
		})

	# Rank by score descending; smaller rank is better (1 = top)
	ranked = sorted([x for x in results if x.get("rank") is None], key=lambda z: z["score"], reverse=True)
	for idx, item in enumerate(ranked, start=1):
		item["rank"] = idx

	# Include any not-found entries at the end preserving their order
	not_found = [x for x in results if x.get("reason") == "HCP id not found"]
	final = ranked + not_found
	return final


@tool
def save_json(data: List[Dict[str, Any]], path: str = OUTPUT_FILE) -> str:
	with open(path, "w") as f:
		json.dump(data, f, indent=2)
	return path


def _tools_list() -> List[Any]:
	return [read_personalized_csv, analyze_hcps, save_json]


def create_agent() -> Agent:
	return Agent(
		system_prompt="""
		You are Content-Agent (MOA & KOL engagement analyzer).

		Task:
		1) Read the personalized HCP engagement data using the provided tools.
		2) For a given list of `hcp_id`s, analyze `moa_email_summary`, `clicked_kol_video_flag`, and `kol_video_summary`.
		3) Rank the HCPs by engagement and return a JSON array with `hcp_id`, `rank`, `score`, `reason`, and `details`.
		4) Use the tools `read_personalized_csv`, `analyze_hcps`, and `save_json` where appropriate.
		Return only the JSON array as the final output.
		""",
		tools=_tools_list(),
	)


agent = create_agent()


def run_content_agent(hcp_ids: List[str]) -> List[Dict[str, Any]]:
	"""Runner that uses the tools and agent to produce rank JSON for provided hcp_ids."""
	# Fetch records
	records = read_personalized_csv()

	# Try using the agent first (agents may call tools); pass data and hcp_ids
	instruction = (
		"Analyze the provided records and return the ranked JSON array for the given hcp_ids."
	)
	try:
		agent_result = agent(instruction, records=records, hcp_ids=hcp_ids)
		# Agent implementations may return .text or string
		text_out = getattr(agent_result, "text", None) or str(agent_result)
		try:
			parsed = json.loads(text_out)
		except Exception:
			# Fallback to local analyzer tool
			parsed = analyze_hcps(records, hcp_ids)
	except Exception:
		parsed = analyze_hcps(records, hcp_ids)

	# Save output locally
	save_json(parsed, OUTPUT_FILE)
	return parsed


if __name__ == "__main__":
	import sys

	if len(sys.argv) < 2:
		print("Usage: python content_agent.py HCP_ID [HCP_ID ...]")
		sys.exit(1)
	hcp_ids = sys.argv[1:]
	out = run_content_agent(hcp_ids)
	print(json.dumps(out, indent=2))

