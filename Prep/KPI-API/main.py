# main.py
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from typing import Any, Dict, Optional
from utils import execute_redshift_sql
from KPI.queries import kpi_overview_sql
from mangum import Mangum
import logging
load_dotenv()
cors_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in cors_origins_env.split(",")
    if origin.strip()
]
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hcp_kpi_api")

app = FastAPI(title="HCP KPI API (Production)", version="1.0",root_path="/v1")

if ALLOWED_ORIGINS:
    logger.info("CORS enabled for origins: %s", ALLOWED_ORIGINS)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    logger.warning("CORS_ALLOW_ORIGINS is empty. No CORS origins allowed.")


def safe_number(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", "")
        if s == "":
            return None
        if s.lower() in ("true", "false"):
            return 1.0 if s.lower() == "true" else 0.0
        return float(s)
    except Exception:
        return None


def build_response_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    # ---- PRE-CALL KPIs ----
    total_hcps = safe_number(row.get("total_hcps_global"))
    total_interacted_hcps = int(safe_number(row.get("total_interacted_hcps_by_user") or 0))
    followup_emails_sent = int(safe_number(row.get("followup_emails_sent_by_user") or 0))
    scheduled_calls_next_7d = int(safe_number(row.get("scheduled_calls_next_7d") or 0))

    # ---- POST-CALL KPIs ----
    action_items_pending = int(safe_number(row.get("action_items_pending") or 0))
    sample_request_qty_30d = int(safe_number(row.get("sample_request_qty_30d") or 0))
    followups_sent_last_30d = int(safe_number(row.get("followups_sent_last_30d") or 0))
    total_hcp_contacted_today = int(safe_number(row.get("total_hcp_contacted_today") or 0))

    return {
        "pre_call_kpis": {
            "total_hcps": total_hcps,
            "total_interacted_hcps": total_interacted_hcps,
            "followup_emails_sent": followup_emails_sent,
            "scheduled_calls_next_7d": scheduled_calls_next_7d
        },
        "post_call_kpis": {
            "action_items_pending": action_items_pending,
            "sample_request_qty_30d": sample_request_qty_30d,
            "followups_sent_last_30d": followups_sent_last_30d,
            "total_hcp_contacted_today": total_hcp_contacted_today
        }
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/kpi/overview")
def kpi_overview(user_id: str = Query(..., description="username, (e.g. vivek.kumar) used to scope user-level KPIs")):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    username=user_id.lower()
    sql = kpi_overview_sql(username)
    resp = execute_redshift_sql(sql)

    if resp.get("status") != "finished":
        detail = {
            "status": resp.get("status"),
            "message": resp.get("message"),
            "statement_id": resp.get("statement_id")
        }
        logger.error("KPI query failed: %s", detail)
        raise HTTPException(status_code=500, detail=detail)

    rows = resp.get("rows", [])
    if not rows:
        return {"message": "no data", "dashboard": {}}

    dashboard = build_response_from_row(rows[0])
    logger.info("KPI served successfully for user=%s", user_id)
    return dashboard

handler = Mangum(app)