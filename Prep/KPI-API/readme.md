# HCP KPI API – Username-Based User Mapping

## Overview
This service exposes a FastAPI endpoint that returns **pre-call** and **post-call KPIs** for HCPs (Healthcare Professionals) scoped to a **user**.  
The system has been updated to use **username-based identifiers** instead of numeric user IDs.

Numeric IDs like `101`, `102`, etc. are **no longer supported**.

---

## Key Change
**Before**
user_id = 101

**Now**
user_id = vivek.kumar

All usernames:
- are **lowercase**
- are stored in `hcp_user_mapping.user_id`
- are passed directly to the API

---


.env

---
must have Allowd domain, if accessing from outside domain;
# Comma-separated list of allowed frontend origins
CORS_ALLOW_ORIGINS=http://localhost:5173

## Supported Usernames
vivek.kumar, nikhil.patel, govind.ghuge, bidhan.laha, shresth.p,
palash.gupta, nikhil.sunil, akshit.goel, jaideep.jahagirdar

All usernames:
- are **lowercase**
- are stored in `hcp_user_mapping.user_id`
- are passed directly to the API

---

## Database
### Table Used
hcp_user_mapping


### Schema (relevant column)
| column  | type    | description |
|-------|---------|-------------|
| user_id | varchar | username (lowercase) |
| hcp_id  | varchar | HCP identifier |

Each username can map to multiple HCPs.

---

## API Endpoints

### Health Check
```http
GET /health
Response:
{ "status": "ok" }

KPI Overview
GET /kpi/overview?user_id=<username>

Example
curl "http://localhost:8000/kpi/overview?user_id=vivek.kumar"

Successful Response

{
  "pre_call_kpis": {
    "total_hcps": 1500,
    "total_interacted_hcps": 12,
    "followup_emails_sent": 4,
    "scheduled_calls_next_7d": 3
  },
  "post_call_kpis": {
    "action_items_pending": 6,
    "sample_request_qty_30d": 18,
    "followups_sent_last_30d": 2,
    "total_hcp_contacted_today": 0
  }
}


Running the Service

uvicorn main:app --host 0.0.0.0 --port 8000 --reload
