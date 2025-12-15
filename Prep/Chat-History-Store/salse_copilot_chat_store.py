import json
import boto3
import decimal
import logging
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key, Attr
import base64 as _b64


# ---------- Logging Setup ----------
LOGGER = logging.getLogger()
if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER.setLevel(logging.INFO)


AWS_REGION = "us-east-1"

def _ssm():
    return boto3.client("ssm", region_name=AWS_REGION)

def get_parameter_value(parameter_name: str, decrypt: bool = True) -> str | None:
    if not parameter_name:
        return None
    try:
        resp = _ssm().get_parameter(Name=parameter_name, WithDecryption=decrypt)
        return resp["Parameter"]["Value"]
    except Exception as e:
        LOGGER.warning(f"SSM get_parameter failed for {parameter_name}: {e}")
        return None

def log_event(event, note="event"):
    try:
        snippet = json.dumps(event)[:2000]
        LOGGER.debug(f"{note}: {snippet}")
    except Exception:
        LOGGER.debug(f"{note}: <unserializable>")

dynamodb = boto3.resource("dynamodb")
SESSION_TABLE_NAME = get_parameter_value("SC_CHAT_SESSIONS_TABLE")
MESSAGE_TABLE_NAME = get_parameter_value("SC_CHAT_MESSAGES_TABLE")

sessions = dynamodb.Table(SESSION_TABLE_NAME)
messages = dynamodb.Table(MESSAGE_TABLE_NAME)


# -------- Utilities ---------

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def epoch_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def json_default(obj):
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return str(obj)

def response(code, body):
    LOGGER.info(f"Response status={code}")
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body, default=json_default)
    }


# -------- HTTP API v1 Parsing ---------

def normalize_path(raw_path: str, event: dict) -> str:
    """
    Remove stage prefix (/v1, /prod, /$default) if present and trim trailing slash.
    """
    if not raw_path:
        return "/"
    # Extract stage from event if available
    stage = (
        event.get("requestContext", {}).get("stage")
        or event.get("requestContext", {}).get("http", {}).get("stage")
    )
    # Strip leading stage segment like "/v1/..." or "/prod/..."
    if stage and raw_path.startswith(f"/{stage}/"):
        raw_path = raw_path[len(stage) + 1:]  # remove "/stage"
        if not raw_path.startswith("/"):
            raw_path = "/" + raw_path
    # Also handle exact "/stage" (no trailing path)
    if stage and raw_path == f"/{stage}":
        raw_path = "/"
    # Trim trailing slash (except root)
    if len(raw_path) > 1 and raw_path.endswith("/"):
        raw_path = raw_path[:-1]
    return raw_path

def parse_event(event):
    """
    Supports API Gateway HTTP API payload v1.0 and v2.0.
    Returns: method, path, qs, body
    """
    # Method
    method = event.get("httpMethod") \
        or event.get("requestContext", {}).get("http", {}).get("method")
    # Raw path
    raw_path = event.get("path") or event.get("rawPath") or "/"
    path = normalize_path(raw_path, event)
    # Query params
    qs = event.get("queryStringParameters") or {}
    # Body (handle base64 too)
    body_raw = event.get("body")
    if event.get("isBase64Encoded"):
        try:
            body_raw = _b64.b64decode(body_raw or "").decode("utf-8")
        except Exception:
            pass
    try:
        body = json.loads(body_raw) if body_raw else {}
    except Exception:
        body = {}
    LOGGER.info(f"Parsed version={event.get('version')} method={method} path={path} qs={qs}")
    return method, path, qs, body


def get_user_id(qs, body, headers):
    if qs.get("user_id"):
        return qs["user_id"]
    if body.get("user_id"):
        return body["user_id"]
    if headers.get("x-user-id"):
        return headers["x-user-id"]
    return None


# -------- DynamoDB Ops ---------

def create_session(session_id, user_id, agent_id, title):
    item = {
        "session_id": session_id,
        "user_id": user_id,
        "agent_id": agent_id,
        "title": title or "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "last_message_preview": ""
    }
    sessions.put_item(Item=item)
    LOGGER.info(f"Session created session_id={session_id} user_id={user_id} agent_id={agent_id}")
    return item

def list_sessions(user_id, agent_id=None):
    params = {
        "IndexName": "user_id-index",
        "KeyConditionExpression": Key("user_id").eq(user_id),
        "ScanIndexForward": False
    }
    if agent_id:
        params["FilterExpression"] = Attr("agent_id").eq(agent_id)

    resp = sessions.query(**params)
    LOGGER.info(f"Listed {len(resp.get('Items', []))} sessions for user_id={user_id} agent_id={agent_id}")
    return resp.get("Items", [])

def get_session(session_id, user_id):
    resp = sessions.get_item(Key={"session_id": session_id})
    item = resp.get("Item")
    if not item or item["user_id"] != user_id:
        LOGGER.warning(f"Session not found or mismatch session_id={session_id} user_id={user_id}")
        return None
    LOGGER.info(f"Session retrieved session_id={session_id}")
    return item

def add_message(session_id, role, content):
    ts = epoch_ms()
    messages.put_item(
        Item={
            "session_id": session_id,
            "message_timestamp": ts,
            "role": role,
            "content": content
        }
    )
    sessions.update_item(
        Key={"session_id": session_id},
        UpdateExpression="SET updated_at = :u, last_message_preview = :p",
        ExpressionAttributeValues={
            ":u": now_iso(),
            ":p": content[:500]
        }
    )
    LOGGER.info(f"Message added session_id={session_id} role={role} ts={ts}")

def fetch_messages(session_id):
    resp = messages.query(
        KeyConditionExpression=Key("session_id").eq(session_id),
        ScanIndexForward=True
    )
    LOGGER.info(f"Fetched {len(resp.get('Items', []))} messages session_id={session_id}")
    return resp.get("Items", [])


# -------- MAIN HANDLER (HTTP API v1) ---------

def lambda_handler(event, context):
    try:
        log_event(event, "incoming")
        method, path, qs, body = parse_event(event)
        headers = event.get("headers") or {}

        user_id = get_user_id(qs, body, headers)
        LOGGER.info(f"Dispatch method={method} path={path} user_id={user_id}")

        if method == "OPTIONS":
            return response(200, {"ok": True})

        # POST /sessions
        if method == "POST" and path == "/sessions":
            if not user_id:
                return response(400, {"error": "user_id required"})
            if "session_id" not in body or "agent_id" not in body:
                return response(400, {"error": "session_id and agent_id required"})
            item = create_session(
                body["session_id"],
                user_id,
                body["agent_id"],
                body.get("title", "")
            )
            return response(201, {"session": item})

        # GET /sessions
        if method == "GET" and path == "/sessions":
            if not user_id:
                return response(400, {"error": "user_id required"})
            items = list_sessions(user_id, qs.get("agent_id"))
            return response(200, {"sessions": items})

        # GET /sessions/{id}
        if method == "GET" and path.startswith("/sessions/") and not path.endswith("/messages"):
            if not user_id:
                return response(400, {"error": "user_id required"})
            session_id = path.replace("/sessions/", "")
            sess = get_session(session_id, user_id)
            if not sess:
                return response(404, {"error": "not found"})
            msgs = fetch_messages(session_id)
            return response(200, {"session": sess, "messages": msgs})

        # POST /sessions/{id}/messages
        if method == "POST" and path.startswith("/sessions/") and path.endswith("/messages"):
            if not user_id:
                return response(400, {"error": "user_id required"})
            session_id = path.replace("/sessions/", "").replace("/messages", "")
            if "role" not in body or "content" not in body:
                return response(400, {"error": "role and content required"})
            add_message(session_id, body["role"], body["content"])
            return response(201, {"ok": True})

        LOGGER.warning(f"Route not found method={method} path={path}")
        return response(404, {"error": "route not found"})

    except Exception as e:
        LOGGER.exception("Unhandled error")
        return response(500, {"error": str(e)})
