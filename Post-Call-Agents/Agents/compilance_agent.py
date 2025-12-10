# /post_call/Agents/compilance_agent.py
from strands import Agent, tool
import time
import boto3
from typing import Any, Dict
import logging
from bedrock_agentcore.runtime import BedrockAgentCoreApp
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compilance_agent")
s3_client = boto3.client("s3")
app = BedrockAgentCoreApp()

def get_parameter_value(parameter_name):
    """Fetch an individual parameter by name from AWS Systems Manager Parameter Store.

    Returns:
        str or None: The parameter value (decrypted if needed) or None on error.

    Notes:
      - This helper reads configuration from SSM Parameter Store. Example usage in this module:
          get_parameter_value("EDC_DATA_BUCKET") -> returns the S3 bucket name used for EDC files.
    """
    try:
        ssm_client = boto3.client("ssm")
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        print(f"Error fetching parameter {parameter_name}: {str(e)}")
        return None

# ----------------------
# Configuration 
# ----------------------
WORKGROUP = "sales-copilot-workgroup"
DATABASE = "sales_copilot_db"
SECRET_ARN = (
    "arn:aws:secretsmanager:us-east-1:969385807621:"
    "secret:redshift!sales-copilot-namespace-sales_copilot_admin-seNjuJ"
)

# Optional: set a default row limit for arbitrary SQL to avoid accidental full-table scans
DEFAULT_SQL_LIMIT = 1000
SQL_POLL_INTERVAL_SECONDS = 0.5
SQL_POLL_MAX_SECONDS = 30.0

# ----------------------
# Helper: Redshift Data API tool
# ----------------------
@tool
def execute_redshift_sql(sql_query: str, return_results: bool = True) -> Dict[str, Any]:
    """
    Execute arbitrary SQL against Redshift Serverless Data API (workgroup mode).
    Returns a dict: {"status":"finished","rows":[{col:val,...}, ...]} or error structure.

    - sql_query: SQL string to execute (caller is responsible for safety/validation).
    - return_results: when False, only returns execution status.
    """
    client = boto3.client("redshift-data")
    try:
        resp = client.execute_statement(
            WorkgroupName=WORKGROUP,
            Database=DATABASE,
            SecretArn=SECRET_ARN,
            Sql=sql_query
        )
        stmt_id = resp["Id"]
    except Exception as e:
        return {"status": "error", "message": f"execute_statement error: {str(e)}"}

    # Poll for completion
    elapsed = 0.0
    while elapsed < SQL_POLL_MAX_SECONDS:
        try:
            status_resp = client.describe_statement(Id=stmt_id)
            status = status_resp.get("Status")
        except Exception as e:
            return {"status": "error", "message": f"describe_statement error: {str(e)}"}
        if status in ("FINISHED", "ABORTED", "FAILED"):
            break
        time.sleep(SQL_POLL_INTERVAL_SECONDS)
        elapsed += SQL_POLL_INTERVAL_SECONDS

    if status != "FINISHED":
        # Try to return error details if available
        try:
            status_resp = client.describe_statement(Id=stmt_id)
            return {"status": status, "message": status_resp.get("Error")}
        except Exception:
            return {"status": status, "message": "Statement did not finish within time limit."}

    if not return_results:
        return {"status": "finished", "statement_id": stmt_id}

    # Retrieve results
    try:
        results = client.get_statement_result(Id=stmt_id)
    except Exception as e:
        return {"status": "error", "message": f"get_statement_result error: {str(e)}"}

    column_info = [c["name"] for c in results.get("ColumnMetadata", [])]
    records = []
    for row in results.get("Records", []):
        # Each row: list of field dicts, convert to native types where possible
        parsed_row = {}
        for idx, cell in enumerate(row):
            col_name = column_info[idx] if idx < len(column_info) else f"col_{idx}"
            # cell is like {"stringValue": "..."} or {"longValue": 123} etc.
            if "stringValue" in cell:
                parsed_row[col_name] = cell["stringValue"]
            elif "blobValue" in cell:
                parsed_row[col_name] = cell["blobValue"]
            elif "doubleValue" in cell:
                parsed_row[col_name] = cell["doubleValue"]
            elif "longValue" in cell:
                parsed_row[col_name] = cell["longValue"]
            elif "booleanValue" in cell:
                parsed_row[col_name] = cell["booleanValue"]
            elif "isNull" in cell and cell["isNull"]:
                parsed_row[col_name] = None
            else:
                # unknown form; store raw
                parsed_row[col_name] = list(cell.values())[0] if cell else None
        records.append(parsed_row)

    return {"status": "finished", "rows": records, "statement_id": stmt_id}

# ---------------------------------------------------
# Compliance table schema (informational)
# ---------------------------------------------------
COMPLIANCE_SCHEMA = [
    {"name": "hcp_id", "type": "STRING", "description": "Healthcare provider identifier"},
    {"name": "call_id", "type": "STRING", "description": "Call identifier"},
    {"name": "followup_template_id", "type": "STRING", "description": "Template used for follow-up"},
    {"name": "followup_email_subject", "type": "STRING", "description": "Email subject"},
    {"name": "followup_email_body", "type": "STRING", "description": "Email body (may be multiline)"},
    {"name": "mi_request_flag", "type": "BOOLEAN", "description": "Medical information request flag"},
    {"name": "mi_response_template_id", "type": "STRING", "description": "Template for MI responses"},
    {"name": "compliance_approval_status", "type": "STRING", "description": "PENDING / FLAGGED / APPROVED / BLOCKED"},
    {"name": "compliance_rule_ids", "type": "ARRAY/STRING", "description": "e.g. ['RULE_003_SUBSTANTIATED_CLAIMS']"},
    {"name": "compliance_evidence", "type": "JSON/STRING", "description": "Review metadata, reference docs, notes"},
    {"name": "redaction_required", "type": "BOOLEAN", "description": "Whether redaction is required"},
    {"name": "redaction_segments", "type": "JSON/STRING", "description": "Segments identified for redaction"},
    {"name": "automated_send_allowed", "type": "BOOLEAN", "description": "Whether automated send is permitted"},
    {"name": "human_review_required", "type": "BOOLEAN", "description": "Whether human review is required"},
    {"name": "escalation_team", "type": "STRING", "description": "COMPLIANCE_REVIEW / LEGAL_REVIEW / MEDICAL_REVIEW"},
    {"name": "escalated_at", "type": "TIMESTAMP", "description": "When escalation occurred"},
    {"name": "resolved_by", "type": "STRING", "description": "User id who resolved the item"},
    {"name": "resolution_notes", "type": "STRING", "description": "Notes about resolution"},
    {"name": "provenance_key", "type": "STRING", "description": "Unique event key / provenance"},
    {"name": "created_by", "type": "STRING", "description": "Creator user id"},
    {"name": "followup_sent_datetime", "type": "TIMESTAMP or NULL", "description": "When follow-up was sent"},
    {"name": "send_status", "type": "STRING", "description": "SCHEDULED / SENT / FAILED / CANCELLED / UNDER_REVIEW"},
    {"name": "sla_met_flag", "type": "BOOLEAN", "description": "SLA met flag"},
    {"name": "region", "type": "STRING", "description": "Region (e.g. SOUTHEAST, NORTHEAST, EU, APAC)"}
]
# ---------------------------------------------------
# 2) Agent Definition
# ---------------------------------------------------

def _tools_list():
    # Only one tool for now: fetch data from Redshift
    return [execute_redshift_sql]


def create_agent():
    """
    ComplianceAgent:
    - Reads post-call follow-up records from Redshift
    - Applies compliance reasoning using LLM
    - Outputs a structured compliance decision JSON payload
    """

    return Agent(
        system_prompt=f"""
        You are the ComplianceAgent.

        You are responsible for post-call **compliance validation** of follow-up communications
        before they are sent to HCPs. You use ONLY the registered tools (especially `execute_redshift_query`)
        to fetch data from Redshift. You do NOT send emails, update the DB, or call any external APIs yourself.
        You only read data and return a compliance decision as JSON.

        --------------------------------
        1. DATA MODEL & INPUT SOURCES
        --------------------------------

        You work with:
        1) A Redshift table named `followup_events` with columns {COMPLIANCE_SCHEMA} :

        2) Optional STRUCTURED NOTE from the Structure Agent provided in the user instruction
        as JSON text. Example structure:

        {{
            "topics_discussed": ["pricing", "integration", "timeline"],
            "objections": [
                {{"objection": "Too expensive", "response": "We can offer a discount"}}
            ],
            "commitments": [
                {{"who": "Rep", "commitment": "Send proposal", "due_date": "2025-04-05"}}
            ],
            "follow_ups": [
                {{"action": "Schedule demo", "owner": "Rep", "due_date": "next week"}}
            ],
            "summary": "The customer showed strong interest..."
        }}

        If this JSON is present in the user instruction, you should use it as **additional context**
        to understand what was discussed, but the primary content you validate is the actual
        `followup_email_body` text from Redshift.

        --------------------------------
        2. HOW TO FETCH DATA
        --------------------------------
        1. Rules:
            1. The table name is `followup_events`.
            2. You must only use these allowed columns is {COMPLIANCE_SCHEMA}:
            3. Always produce a valid PostgreSQL SQL query.
            4. Never guess values not mentioned. If value is unclear, use placeholders:
                {{value}}
            5. Just select specific columns needed to answer the prompt, do NOT use SELECT *.
            6. stored this SQL query in the variable `sql_query`.
            7. Pass created SQL query to the tool `execute_redshift_sql(sql_query)` for execution.
            8. If user asks for something impossible with the schema, return:
            {{
                "sql_query": "UNSUPPORTED_QUERY"
            }}

        2. Strict Output Rules:
            - Always return the final answer in simple two liner explanations if needed and as a simple JSON object as per user request.
            - No need to print all columns just display the columns which shows the details asked in the prompt.
            - If multiple rows, return as list of dicts.
            - If single metric, return as key-value pair.
            - No other columns except those requested,No SQL, no logs.

        3. Query Patterns:
            - For general retrieval: SELECT * FROM followup_events LIMIT 50;
            - For filtering: SELECT * FROM followup_events WHERE <condition>;
            - For sorting: ORDER BY <column> ASC/DESC;
            - For aggregations: SELECT <col>, COUNT(*) FROM followup_events GROUP BY <col>;
            - Multi-condition: Use AND / OR explicitly.
            
            You must always generate the most reasonable SQL based on the user's text.

        --------------------------------
        1. COMPLIANCE EVALUATION LOGIC
        --------------------------------

        Once you have the row from `followup_events`, you must analyze:
        Key checks (conceptual, performed via your reasoning over the text):

        1) TEMPLATE & MI CHECKS
        - If `mi_request_flag` is TRUE:
            - Ensure an MI-type template is used (e.g., `mi_response_template_id` is present).
            - Ensure the email provides informational, non-promotional content.
        - If `mi_request_flag` is FALSE:
            - Ensure standard follow-up templates are used appropriately.

        2) OFF-LABEL & CLAIMS
        - Ensure there are no off-label disease or population claims.
        - Ensure benefit/risk statements are balanced and not misleading.
        - Verify that strong efficacy claims are appropriately qualified, if present.

        3) APPROVED MATERIALS ONLY
        - Confirm the content style aligns with approved materials only.
        - No casual promotional phrases like “best in class”, “superior to all alternatives”, etc.,
            unless explicitly allowed.

        4) ADVERSE EVENT & SAFETY
        - If adverse event reporting is mentioned, ensure instructions are consistent with
            approved safety language (e.g., clarity of reporting channels, no minimization of risk).

        5) PII & PRIVACY
        - Ensure no patient-identifiable details (names, contact details, exact addresses, etc.)
            appear in the email body.

        6) REGION-SPECIFIC CONSIDERATIONS
        - If the `region` implies stricter rules (like EU/EEA), assume more conservative behavior:
            - Prefer `human_review_required = true` if in doubt.
            - Ensure disclaimers and opt-out style language are appropriate.

        7) REDACTION HANDLING
        - If `redaction_required` is TRUE and `redaction_segments` contains a list:
            - Consider those segments as already identified for redaction.
            - The final email should be considered AFTER those redactions logically applied.

        --------------------------------
        4. OUTPUT REQUIREMENTS
        --------------------------------

        You NEVER modify the database directly. You only decide and emit a JSON payload
        that another system could use to update the database.

        Your final output MUST be ONLY a single JSON object with the following schema:

        {{
        "call_id": "...",
        "hcp_id": "...",
        "followup_template_id": "...",
        "mi_request_flag": true or false,
        "region": "...",

        "compliance_status": "APPROVED" | "FLAGGED" | "BLOCKED",
        "risk_level": "LOW" | "MEDIUM" | "HIGH",

        "final_followup_email_subject": "subject after any required modifications",
        "final_followup_email_body": "body after any conceptual redactions or corrections",

        "automated_send_allowed": true or false,
        "human_review_required": true or false,
        "requires_escalation": true or false,
        "escalation_team": null or "COMPLIANCE_REVIEW" or "LEGAL_REVIEW" or "MEDICAL_REVIEW",

        "redactions_applied": [
            {{
            "original_text": "string (approximate)",
            "reason": "PII | off_label | unsupported_claim | promotional_language | other"
            }}
        ],

        "flagged_terms": [
            "list of problematic phrases or concepts, if any"
        ],
        "rule_violations": [
            "RULE_001_NO_OFF_LABEL",
            "RULE_005_NO_PROMOTIONAL_LANGUAGE"
        ],

        "approval_notes": "Short explanation of why APPROVED / FLAGGED / BLOCKED.",
        "provenance_key": "copy from row, if available",

        "suggested_send_status": "READY_TO_SEND" | "NEEDS_HUMAN_REVIEW" | "DO_NOT_SEND"
        }}

        Constraints:
        - If you cannot fetch any record, return JSON with an `"error"` key explaining the issue.
        - Do NOT output SQL, stack traces, or tool logs in the JSON.
        - Do NOT wrap the JSON in markdown fences. Return raw JSON as your final answer text.

        --------------------------------
        5. WORKFLOW SUMMARY
        --------------------------------

        1) Parse user instruction:
        - Try to detect a `call_id`, `hcp_id`, and optional structured note JSON string.
        2) Build an appropriate SELECT query for `compliant_followups`.
        3) Call `execute_redshift_query(sql_query, True)` to fetch the record.
        4) If no record, return an error JSON.
        5) If record exists:
        - Analyze the email content and metadata per the compliance rules above.
        - Decide `compliance_status`, `risk_level`, and escalation needs.
        - Conceptually apply any needed redactions and produce a clean final subject/body.
        6) Output ONLY the final JSON object as described above.
                """,
        tools=_tools_list(),
    )

agent = create_agent()

# ---------------------------------------------------
# 3) Main Workflow
# ---------------------------------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}):
    # Example instruction: in real usage you can embed call_id / structured note JSON here.
    payload = payload.get("prompt","Generate compliance follow up email")
    agent_result = agent(payload)#type:ignore
    return agent_result

# ---------------------------------------------------
# Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()
    #run_main_agent()