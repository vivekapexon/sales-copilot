import json
import boto3
import decimal
import logging
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key, Attr
import base64
from typing import NamedTuple

# ---------- Logging Setup ----------
LOGGER = logging.getLogger()
if not LOGGER.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER.setLevel(logging.INFO)

AWS_REGION = "us-east-1"

# Create SSM client once at module level for performance
_ssm_client = boto3.client("ssm", region_name=AWS_REGION)

def _ssm():
    return _ssm_client

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
    except Exception as e:
        LOGGER.debug(f"{note}: <unserializable> - {e}")

dynamodb = boto3.resource("dynamodb")
SESSION_TABLE_NAME = get_parameter_value("SC_CHAT_SESSIONS_TABLE")
MESSAGE_TABLE_NAME = get_parameter_value("SC_CHAT_MESSAGES_TABLE")

if not SESSION_TABLE_NAME or not MESSAGE_TABLE_NAME:
    raise ValueError("Required DynamoDB table names not found in SSM parameters")

sessions = dynamodb.Table(SESSION_TABLE_NAME)
messages = dynamodb.Table(MESSAGE_TABLE_NAME)

# -------- Utilities ---------

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def epoch_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def json_default(obj):
    if isinstance(obj, decimal.Decimal):
        return int(obj) if obj == int(obj) else float(obj)
    return str(obj)

def response(code, body):
    LOGGER.info(f"Response status={code}")
    return {
        "statusCode": code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS"
        },
        "body": json.dumps(body, default=json_default)
    }

# -------- HTTP API v1 Parsing ---------

class ParsedEvent(NamedTuple):
    method: str
    path: str
    qs: dict
    body: dict

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
        raw_path = raw_path[len(stage) + 2:]  # remove "/stage/"
        if not raw_path.startswith("/"):
            raw_path = "/" + raw_path
    # Also handle exact "/stage" (no trailing path)
    if stage and raw_path == f"/{stage}":
        raw_path = "/"
    # Trim trailing slash (except root)
    if len(raw_path) > 1 and raw_path.endswith("/"):
        raw_path = raw_path[:-1]
    return raw_path

def parse_event(event) -> ParsedEvent:
    """
    Supports API Gateway HTTP API payload v1.0 and v2.0.
    Returns: ParsedEvent with method, path, qs, body
    """
    import base64 as _b64
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
        except Exception as e:
            LOGGER.warning(f"Failed to decode base64 body: {e}")
    try:
        body = json.loads(body_raw) if body_raw else {}
    except json.JSONDecodeError as e:
        LOGGER.warning(f"Failed to parse JSON body: {e}")
        body = {}
    LOGGER.info(f"Parsed version={event.get('version')} method={method} path={path} qs={qs}")
    return ParsedEvent(method, path, qs, body)

def get_user_id(qs, body, headers):
    if qs.get("user_id"):
        return qs["user_id"]
    if body.get("user_id"):
        return body["user_id"]
    if headers.get("x-user-id"):
        return headers["x-user-id"]
    return None

def extract_session_id(path: str) -> str:
    """Safely extract session ID from path"""
    parts = path.split('/')
    if len(parts) >= 3 and parts[1] == 'sessions':
        return parts[2]
    return ""

# -------- DynamoDB Ops ---------

def create_session(session_id, user_id, agent_id, title):
    if not all([session_id, user_id, agent_id]):
        raise ValueError("session_id, user_id, and agent_id are required")
    
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
    if not user_id:
        raise ValueError("user_id is required")
    
    params = {
        "IndexName": "user_id-index",
        "KeyConditionExpression": Key("user_id").eq(user_id),
        "ScanIndexForward": False
    }
    if agent_id:
        params["FilterExpression"] = Attr("agent_id").eq(agent_id)

    all_items = []
    last_key = None
    
    while True:
        if last_key:
            params["ExclusiveStartKey"] = last_key
        
        resp = sessions.query(**params)
        all_items.extend(resp.get("Items", []))
        
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
    
    LOGGER.info(f"Listed {len(all_items)} sessions for user_id={user_id} agent_id={agent_id}")
    return all_items

def get_session(session_id, user_id):
    if not session_id or not user_id:
        return None
    
    resp = sessions.get_item(Key={"session_id": session_id})
    item = resp.get("Item")
    if not item or item["user_id"] != user_id:
        LOGGER.warning(f"Session not found or mismatch session_id={session_id} user_id={user_id}")
        return None
    LOGGER.info(f"Session retrieved session_id={session_id}")
    return item

def add_message(session_id, role, content):
    if not all([session_id, role, content]):
        raise ValueError("session_id, role, and content are required")
    
    if role not in ["user", "assistant", "system"]:
        raise ValueError("role must be one of: user, assistant, system")
    
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
    if not session_id:
        return []
    
    resp = messages.query(
        KeyConditionExpression=Key("session_id").eq(session_id),
        ScanIndexForward=True
    )
    LOGGER.info(f"Fetched {len(resp.get('Items', []))} messages session_id={session_id}")
    return resp.get("Items", [])

def delete_session_cascade(session_id, user_id):
    if not session_id or not user_id:
        return False
    
    sess = get_session(session_id, user_id)
    if not sess:
        return False
    
    # Batch delete messages with pagination
    last_key = None
    total_deleted = 0
    
    while True:
        params = {
            "KeyConditionExpression": Key("session_id").eq(session_id),
            "Limit": 25
        }
        if last_key:
            params["ExclusiveStartKey"] = last_key
        
        resp = messages.query(**params)
        items = resp.get("Items", [])
        
        if not items:
            break
        
        with messages.batch_writer() as batch:
            for msg in items:
                batch.delete_item(Key={"session_id": session_id, "message_timestamp": msg["message_timestamp"]})
        
        total_deleted += len(items)
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
    
    sessions.delete_item(Key={"session_id": session_id})
    LOGGER.info(f"Session cascade deleted session_id={session_id} messages_count={total_deleted}")
    return True

# -------- MAIN HANDLER (HTTP API v1) ---------

def handle_post_sessions(user_id, body):
    if not user_id:
        return response(400, {"error": "user_id required"})
    if "session_id" not in body or "agent_id" not in body:
        return response(400, {"error": "session_id and agent_id required"})
    
    try:
        item = create_session(
            body["session_id"],
            user_id,
            body["agent_id"],
            body.get("title", "")
        )
        return response(201, {"session": item})
    except ValueError as e:
        return response(400, {"error": str(e)})

def handle_get_sessions(user_id, qs):
    if not user_id:
        return response(400, {"error": "user_id required"})
    
    try:
        items = list_sessions(user_id, qs.get("agent_id"))
        return response(200, {"sessions": items})
    except ValueError as e:
        return response(400, {"error": str(e)})

def handle_get_session(user_id, path):
    if not user_id:
        return response(400, {"error": "user_id required"})
    
    session_id = extract_session_id(path)
    if not session_id:
        return response(400, {"error": "invalid session path"})
    
    sess = get_session(session_id, user_id)
    if not sess:
        return response(404, {"error": "not found"})
    
    msgs = fetch_messages(session_id)
    return response(200, {"session": sess, "messages": msgs})

def handle_post_messages(user_id, path, body):
    if not user_id:
        return response(400, {"error": "user_id required"})
    
    session_id = extract_session_id(path)
    if not session_id:
        return response(400, {"error": "invalid session path"})
    
    if "role" not in body or "content" not in body:
        return response(400, {"error": "role and content required"})
    
    try:
        add_message(session_id, body["role"], body["content"])
        return response(201, {"ok": True})
    except ValueError as e:
        return response(400, {"error": str(e)})

def handle_delete_session(user_id, path):
    if not user_id:
        return response(400, {"error": "user_id required"})
    
    session_id = extract_session_id(path)
    if not session_id:
        return response(400, {"error": "invalid session path"})
    
    if delete_session_cascade(session_id, user_id):
        return response(200, {"ok": True})
    return response(404, {"error": "not found"})

def lambda_handler(event, context):
    try:
        log_event(event, "incoming")
        parsed = parse_event(event)
        headers = event.get("headers") or {}

        user_id = get_user_id(parsed.qs, parsed.body, headers)
        LOGGER.info(f"Dispatch method={parsed.method} path={parsed.path} user_id={user_id}")

        if parsed.method == "OPTIONS":
            return response(200, {"ok": True})

        # POST /sessions
        if parsed.method == "POST" and parsed.path == "/sessions":
            return handle_post_sessions(user_id, parsed.body)

        # GET /sessions
        if parsed.method == "GET" and parsed.path == "/sessions":
            return handle_get_sessions(user_id, parsed.qs)

        # GET /sessions/{id}
        if parsed.method == "GET" and parsed.path.startswith("/sessions/") and not parsed.path.endswith("/messages"):
            return handle_get_session(user_id, parsed.path)

        # POST /sessions/{id}/messages
        if parsed.method == "POST" and parsed.path.startswith("/sessions/") and parsed.path.endswith("/messages"):
            return handle_post_messages(user_id, parsed.path, parsed.body)

        # DELETE /sessions/{id}
        if parsed.method == "DELETE" and parsed.path.startswith("/sessions/"):
            return handle_delete_session(user_id, parsed.path)

        LOGGER.warning(f"Route not found method={parsed.method} path={parsed.path}")
        return response(404, {"error": "route not found"})

    except Exception as e:
        LOGGER.exception("Unhandled error")
        return response(500, {"error": "Internal server error"})


if __name__ == "__main__":
    # Test data
    test_user = "test-user-123"
    test_session = "test-session-456"
    test_agent = "test-agent-789"
    
    print("=== API Testing Started ===\n")
    
    # 1. OPTIONS /sessions
    print("1. Testing OPTIONS /sessions")
    options_event = {
        "httpMethod": "OPTIONS",
        "path": "/sessions",
        "queryStringParameters": {},
        "headers": {},
        "body": None
    }
    result = lambda_handler(options_event, None)
    print(f"Result: {result['statusCode']}\n")
    
    # 2. POST /sessions - Create session
    print("2. Testing POST /sessions (Create Session)")
    create_session_event = {
        "httpMethod": "POST",
        "path": "/sessions",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": json.dumps({
            "session_id": test_session,
            "agent_id": test_agent,
            "title": "Test Chat Session"
        })
    }
    result = lambda_handler(create_session_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 3. POST /sessions - Missing fields
    print("3. Testing POST /sessions (Missing Fields)")
    invalid_create_event = {
        "httpMethod": "POST",
        "path": "/sessions",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": json.dumps({"session_id": test_session})
    }
    result = lambda_handler(invalid_create_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 4. GET /sessions - List sessions
    print("4. Testing GET /sessions (List Sessions)")
    list_sessions_event = {
        "httpMethod": "GET",
        "path": "/sessions",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": None
    }
    result = lambda_handler(list_sessions_event, None)
    print(f"Result: {result['statusCode']} - Found {len(json.loads(result['body']).get('sessions', []))} sessions\n")
    
    # 5. GET /sessions with agent filter
    print("5. Testing GET /sessions (With Agent Filter)")
    list_filtered_event = {
        "httpMethod": "GET",
        "path": "/sessions",
        "queryStringParameters": {"user_id": test_user, "agent_id": test_agent},
        "headers": {},
        "body": None
    }
    result = lambda_handler(list_filtered_event, None)
    print(f"Result: {result['statusCode']} - Found {len(json.loads(result['body']).get('sessions', []))} sessions\n")
    
    # 6. GET /sessions/{id} - Get specific session
    print("6. Testing GET /sessions/{id} (Get Session)")
    get_session_event = {
        "httpMethod": "GET",
        "path": f"/sessions/{test_session}",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": None
    }
    result = lambda_handler(get_session_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body']).get('session', {}).get('title', 'N/A')}\n")
    
    # 7. POST /sessions/{id}/messages - Add message
    print("7. Testing POST /sessions/{id}/messages (Add Message)")
    add_message_event = {
        "httpMethod": "POST",
        "path": f"/sessions/{test_session}/messages",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": json.dumps({
            "role": "user",
            "content": "Hello, this is a test message!"
        })
    }
    result = lambda_handler(add_message_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 8. POST /sessions/{id}/messages - Add assistant response
    print("8. Testing POST /sessions/{id}/messages (Assistant Response)")
    add_response_event = {
        "httpMethod": "POST",
        "path": f"/sessions/{test_session}/messages",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": json.dumps({
            "role": "assistant",
            "content": "Hello! I received your test message. How can I help you today?"
        })
    }
    result = lambda_handler(add_response_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 9. POST /sessions/{id}/messages - Invalid role
    print("9. Testing POST /sessions/{id}/messages (Invalid Role)")
    invalid_message_event = {
        "httpMethod": "POST",
        "path": f"/sessions/{test_session}/messages",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": json.dumps({
            "role": "invalid_role",
            "content": "This should fail"
        })
    }
    result = lambda_handler(invalid_message_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 10. GET /sessions/{id} - Get session with messages
    print("10. Testing GET /sessions/{id} (With Messages)")
    get_with_messages_event = {
        "httpMethod": "GET",
        "path": f"/sessions/{test_session}",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": None
    }
    result = lambda_handler(get_with_messages_event, None)
    response_data = json.loads(result['body'])
    print(f"Result: {result['statusCode']} - Session has {len(response_data.get('messages', []))} messages\n")
    
    # 11. DELETE /sessions/{id} - Delete session
    print("11. Testing DELETE /sessions/{id} (Delete Session)")
    delete_session_event = {
        "httpMethod": "DELETE",
        "path": f"/sessions/{test_session}",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": None
    }
    result = lambda_handler(delete_session_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 12. GET /sessions/{id} - Verify deletion
    print("12. Testing GET /sessions/{id} (Verify Deletion)")
    verify_delete_event = {
        "httpMethod": "GET",
        "path": f"/sessions/{test_session}",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": None
    }
    result = lambda_handler(verify_delete_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 13. Error cases - Missing user_id
    print("13. Testing Error Cases (Missing user_id)")
    no_user_event = {
        "httpMethod": "GET",
        "path": "/sessions",
        "queryStringParameters": {},
        "headers": {},
        "body": None
    }
    result = lambda_handler(no_user_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 14. Error cases - Invalid path
    print("14. Testing Error Cases (Invalid Path)")
    invalid_path_event = {
        "httpMethod": "GET",
        "path": "/invalid/path",
        "queryStringParameters": {"user_id": test_user},
        "headers": {},
        "body": None
    }
    result = lambda_handler(invalid_path_event, None)
    print(f"Result: {result['statusCode']} - {json.loads(result['body'])}\n")
    
    # 15. Header-based user_id
    print("15. Testing Header-based user_id")
    header_user_event = {
        "httpMethod": "GET",
        "path": "/sessions",
        "queryStringParameters": {},
        "headers": {"x-user-id": test_user},
        "body": None
    }
    result = lambda_handler(header_user_event, None)
    print(f"Result: {result['statusCode']} - Found {len(json.loads(result['body']).get('sessions', []))} sessions\n")
    
    print("=== API Testing Completed ===")