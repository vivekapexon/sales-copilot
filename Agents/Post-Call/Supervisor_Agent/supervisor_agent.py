"""
Supervisor Agent for Post-Call Intelligence

This module implements a supervisor/orchestrator agent that intelligently 
classifies user intents and delegates tasks to specialized agents for 
post-call analysis including transcription, structure, compliance, 
actions, and sentiment analysis.
"""

import json
import uuid
import boto3
import time
from enum import Enum
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp


# =============================================================================
# AWS Configuration
# =============================================================================
AWS_REGION = "us-east-1"
agentcore_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
app = BedrockAgentCoreApp()


def get_parameter_value(parameter_name: str) -> str:
    """
    Fetch a parameter value from AWS Systems Manager Parameter Store.
    
    Retrieves runtime ARNs and configuration values for agents deployed 
    in AWS Bedrock from SSM Parameter Store with automatic decryption 
    for secure parameters.

    Args:
        parameter_name (str): The name of the parameter to fetch from SSM.

    Returns:
        str: The decrypted parameter value, or None if retrieval fails.
        
    Raises:
        Silently catches and returns None on any SSM API errors.
    """
    try:
        ssm_client = boto3.client("ssm", region_name=AWS_REGION)
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception:
        return None


# =============================================================================
# Agent Runtime ARNs - Fetched from AWS Systems Manager Parameter Store
# =============================================================================
SC_PRC_ACTION_AGENT_RUNTIME_ARN = get_parameter_value("SC_POC_ACTION_AGENT_ARN")
SC_PRC_STRUCTURE_AGENT_RUNTIME_ARN = get_parameter_value("SC_POC_STRUCTURE_AGENT_ARN")
SC_PRC_COMPILANCE_AGENT_RUNTIME_ARN = get_parameter_value("SC_POC_COMPILANCE_AGENT_ARN")
SC_PRC_SENTIMENT_AGENT_RUNTIME_ARN = get_parameter_value("SC_POC_SENTIMENT_AGENT_ARN")
SC_PRC_TRANSCRIPT_AGENT_RUNTIME_ARN = get_parameter_value("SC_POC_TRANSCRIPT_AGENT_ARN")


# =============================================================================
# Supervisor Agent System Prompt
# =============================================================================
SUPERVISOR_AGENT_PROMPT = f"""
You are the Supervisor Agent for Post-Call Intelligence. You intelligently classify user intent and call ONLY the necessary agents.
You NEVER call agents that are not required for the specific user question.
=======================================================================
CLOSED WORLD RULE (ABSOLUTE, NON-NEGOTIABLE)
=======================================================================
You may ONLY use the following Tools/Agents.
This list is FINAL, EXHAUSTIVE, and CLOSED:
1. Transcription Agent
2. Structure Agent
3. Compliance Agent
4. Action Agent
5. Sentiment Agent

NO other tool and agents exists.
You must NOT create, assume, infer, rename, insert, extend, or invent ANY additional agents or analysis beyond these five tools.
============================================================
STEP 1: INTENT CLASSIFICATION (DO THIS FIRST)
============================================================
    Before calling any agent, CLASSIFY the user's NLQ into ONE of these categories.
    Use keyword matching + semantic understanding.
    -------------------------------------------------------------------
    1. **full_post_call_prep** (FULL POST-CALL DELIVERABLES)
    -------------------------------------------------------------------
    Purpose:
    User wants the complete post-call intelligence package (transcription, structure, compliance email, actions, sentiment).
    Keywords:
    "post-call", "full summary", "meeting summary", "follow-up email", "action items",
    "insights", "objections", "next steps", "everything from my call", "post-call prep"
    Call Agents:
    Transcription → Structure → Compliance → Action → Sentiment
    Example NLQs:
    - "Give me the full post-call summary for my call with Dr. Rao"
    - "Post-call prep and follow-up email for Dr. Patel"
    - "Everything from my last call with H123"
    -------------------------------------------------------------------
    2. **transcription_only**
    -------------------------------------------------------------------
    Purpose:
    User wants only the raw transcription of the call.
    Keywords:
    "transcribe", "transcription", "what was said", "audio to text", "transcript"
    Call Agents:
    Transcription Agent ONLY
    Examples:
    - "Transcribe my call with Dr. Mehta"
    - "Give me the transcription for call C789"
    -------------------------------------------------------------------
    3. **structure_only** (CATEGORIZED CALL NOTES & OBJECTIONS)
    -------------------------------------------------------------------
    Purpose:
    User wants structured notes, objections, topics, samples discussed, etc.
    Keywords:
    "call notes", "objections", "key topics", "what was discussed",
    "samples mentioned", "content shared", "structured summary"
    Call Agents:
    Transcription Agent → Structure Agent
    Examples:
    - "What objections did Dr. Sharma raise?"
    - "Show me structured notes from my call with Dr. X"
    -------------------------------------------------------------------
    4. **sentiment_insights_only**
    -------------------------------------------------------------------
    Purpose:
    User wants sentiment, tone, receptivity, relationship stage, risk level.
    Keywords:
    "sentiment", "tone", "receptivity", "relationship stage",
    "next call risk", "objection intensity", "positive negative ratio", "insights"
    Call Agents:
    Transcription Agent → Sentiment Agent
    Examples:
    - "What was the sentiment of my call with Dr. Lee?"
    - "Give me insights and next-call risk for Dr. Patel"
    -------------------------------------------------------------------
    5. **compliance_email_only**
    -------------------------------------------------------------------
    Purpose:
    User wants a compliant follow-up email drafted.
    Keywords:
    "follow-up email", "compliant email", "followup", "email draft",
    "send summary", "compliance email"
    Call Agents:
    Compliance Agent ONLY (transcription optional, passed if available)
    Examples:
    - "Generate a compliant follow-up email for Dr. Johnson"
    - "Draft the follow-up email for my call with H456"
    -------------------------------------------------------------------
    6. **action_items_only**
    -------------------------------------------------------------------
    Purpose:
    User wants extracted action items, commitments, next steps.
    Keywords:
    "action items", "next steps", "commitments", "samples to send",
    "follow-ups", "what I promised", "calendar block"
    Call Agents:
    Transcription Agent → Action Agent
    Examples:
    - "What action items came out of my call with Dr. Rao?"
    - "Did I commit to sending samples to Dr. Y?"
    -------------------------------------------------------------------
    7. **structure_plus_sentiment**
    -------------------------------------------------------------------
    Purpose:
    User wants both structured notes AND sentiment/insights.
    Keywords:
    "summary and insights", "notes and sentiment", "objections and tone"
    Call Agents:
    Transcription Agent → Structure Agent + Sentiment Agent
    Examples:
    - "Give me call notes and sentiment for Dr. Sharma"
    - "Structured summary plus receptivity for H123"
    -------------------------------------------------------------------
    8. **fallback_unsupported**
    -------------------------------------------------------------------
    Purpose:
    NLQ doesn't match anything above.
    Action:
    Return:
    {{ "error": "Unsupported post-call request. Please rephrase." }}
============================================================
STEP 2: EXTRACT REQUIRED PARAMETERS
============================================================
Based on the NLQ, extract:
- hcp_id (required for most queries) and format it into HCP1234 UPPERCASE Followed by digits
- call_id (required for compliance/action when specific call targeted)
- transcription_text (optional, if user pastes it)
- call_date (optional, for disambiguation)
If critical parameters are missing AND cannot be resolved, return:
{{"status": "missing_parameters", "required": ["hcp_id" or "call_id", ...]}}
============================================================
STEP 3: CALL ONLY NECESSARY AGENTS
============================================================
IMPORTANT: Do NOT call agents outside your classified intent.
Dependency rules:
- Structure, Sentiment, Action Agents require transcription_text
- If transcription_text not provided by user → Supervisor MUST call Transcription Agent first
- Compliance Agent can run standalone (does not strictly require transcription)
Example:
  - "Transcribe my call" → Call ONLY Transcription Agent
  - "What objections were raised?" → Transcription → Structure
  - "Generate follow-up email" → Compliance Agent ONLY
  - "Full post-call" → All 5 agents in correct order
============================================================
STEP 4: MERGE & STRUCTURE OUTPUT
============================================================
Combine outputs from called agents ONLY.
Do not invent data from agents you didn't call.
If transcription was fetched internally, pass it downstream but do not duplicate in final output unless requested.
============================================================
STRICT NEGATIVE RULES (NON-NEGOTIABLE)
============================================================
• Do NOT call agents outside the 5 listed above.
• Do NOT call agents not required for the intent.
• Do NOT add parameters tools don't support.
• Do NOT generate data yourself. All facts come from tool outputs.
• Do NOT run Structure/Sentiment/Action without valid transcription.
• If Transcription Agent fails or returns insufficient_data → halt dependent agents.
• Do NOT call all 5 agents unless intent is full_post_call_prep.
• Never hallucinate transcription, notes, or sentiment.
============================================================
AGENT CAPABILITIES (KNOWLEDGE BASE)
============================================================
1. TranscriptionAgent: Returns full transcript + metadata (call_id, timestamps, confidence). May return insufficient_data: true.
2. StructureAgent: Returns categorized objections, key topics, content shared, samples discussed, compliance flags.
3. ComplianceAgent: Returns followup_email_subject, followup_email_body, template_id. Can work with or without transcript.
4. ActionAgent: Returns action_items_json, priority, calendar_block_minutes, primary_action_type.
5. SentimentAgent: Returns quantified sentiment JSON (call_sentiment_score, relationship_stage, next_call_risk_level, etc.).
No other capabilities exist. Do not infer extra functions.
============================================================
FAIL-SAFE LOGIC
============================================================
• If no usable transcription and one is required → return TranscriptionAgent output with insufficiency flag and skip dependent agents.
• If tools return empty/partial data, propagate with low-confidence tagging.
• Never substitute your own invented values.
• Never fabricate fallback "insights" or "notes."
=======================================================================
OUTPUT FORMAT (STRICT)
=======================================================================
Output Rules:
- Use MARKDOWN format ONLY.
- Structure output into these sections:

### 1. DISCRIPTIONS
   - Give the small discription of Doctor first.
 
### 2. SUMMARY  
   - Write a 5-7 lines of summary ONLY based on the data that you fetch from DB.  
   - No external reasoning or added information.
   - NO need to used explicitely another tables, just used tables that mentioned in agents itself.
 
### 3. KEY POINTS 
   - No need to print explicitely. If needed then prints because in other section we used same details.
   - When you print any key points print it in meaningful format so user can understand.
 
###4. KEY INSIGHTS 
   - Give insights in 2-3 lines.
   - Provide insights ONLY from the table and the user's request.  
   - Do not invent or add anything beyond the table content.

### 5. CITATION
   - Provide the source of data from which you fetched the information in citation key.


###  Table heading (If needed to show data in table format)
| hcp_id | territory_id | total_rx_28d | comp_share_28d_delta | formulary_tier_score | priority_score | reason_codes |
|--------|--------------|--------------|----------------------|---------------------|----------------|--------------|
| HCP009 | T-215        | 132          | +2.1%                | 2                   | 92             | GOOD_ACCESS, HIGH_RX |
========================================================================

"""


# =============================================================================
# Agent Tool Definitions
# =============================================================================

@tool
def action_agent_tool(intent: str) -> dict:
    """
    Invoke the Action Agent via Bedrock Agent Runtime.
    
    Extracts action items, commitments, and next steps from call data.
    Generates structured action item lists with priorities and timelines.

    Args:
        intent (str): Natural language prompt describing the action extraction request.

    Returns:
        dict: Agent response containing action items and metadata, or error details.
    """
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    kwargs = {
        "agentRuntimeArn": SC_PRC_ACTION_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception:
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        return {"error": "action_agent_tool invocation failed", "status": "error"}


@tool
def sentiment_agent_tool(intent: str) -> dict:
    """
    Invoke the Sentiment Agent via Bedrock Agent Runtime.
    
    Analyzes call sentiment, tone, receptivity, relationship stage, and risk levels.
    Provides quantified metrics for call quality and HCP engagement.

    Args:
        intent (str): Natural language prompt describing the sentiment analysis request.

    Returns:
        dict: Agent response containing sentiment metrics and insights, or error details.
    """
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    kwargs = {
        "agentRuntimeArn": SC_PRC_SENTIMENT_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception:
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        return {"error": "sentiment_agent_tool invocation failed", "status": "error"}


@tool
def structure_agent_tool(intent: str) -> dict:
    """
    Invoke the Structure Agent via Bedrock Agent Runtime.
    
    Generates structured call notes with categorized objections, key topics, 
    content shared, samples discussed, and compliance flags.

    Args:
        intent (str): Natural language prompt describing the structure extraction request.

    Returns:
        dict: Agent response containing structured call data, or error details.
    """
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    kwargs = {
        "agentRuntimeArn": SC_PRC_STRUCTURE_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception:
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        return {"error": "structure_agent_tool invocation failed", "status": "error"}


@tool
def transcription_agent_tool(intent: str) -> dict:
    """
    Invoke the Transcription Agent via Bedrock Agent Runtime.
    
    Retrieves and processes call transcriptions with metadata including 
    call IDs, timestamps, and confidence scores.

    Args:
        intent (str): Natural language prompt describing the transcription request.

    Returns:
        dict: Agent response containing transcript data and metadata, or error details.
    """
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    kwargs = {
        "agentRuntimeArn": SC_PRC_TRANSCRIPT_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception:
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        return {"error": "transcription_agent_tool invocation failed", "status": "error"}


@tool
def compilance_agent_tool(intent: str) -> dict:
    """
    Invoke the Compliance Agent via Bedrock Agent Runtime.
    
    Generates compliant follow-up emails and ensures communication adherence 
    to regulatory guidelines. Can operate with or without transcript data.

    Args:
        intent (str): Natural language prompt describing the compliance email request.

    Returns:
        dict: Agent response containing email draft and metadata, or error details.
    """
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    kwargs = {
        "agentRuntimeArn": SC_PRC_COMPILANCE_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception:
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        return {"error": "compilance_agent_tool invocation failed", "status": "error"}


# =============================================================================
# Utility Functions
# =============================================================================

def _tools_list() -> list:
    """
    Compile the complete list of available agent tools.
    
    Returns:
        list: Collection of all callable agent tool functions.
    """
    return [
        action_agent_tool,
        sentiment_agent_tool,
        structure_agent_tool,
        transcription_agent_tool,
        compilance_agent_tool
    ]


# =============================================================================
# Agent Initialization
# =============================================================================

def create_supervisor_agent() -> Agent:
    """
    Create and configure the supervisor agent.
    
    Initializes the supervisor agent with the system prompt and list of 
    available tools for intelligent delegation to specialized agents.

    Returns:
        Agent: Configured supervisor agent instance ready for inference.
    """
    return Agent(
        system_prompt=SUPERVISOR_AGENT_PROMPT,
        tools=_tools_list(),
    )


# Instantiate the supervisor agent
agent = create_supervisor_agent()


@app.entrypoint
async def invoke(payload: dict = {}):
    prompt = payload.get("prompt", "")

    try:
        stream = agent.stream_async(prompt)
        async for chunk in stream:
            # Debug: log chunk type and attributes
            print(f"📦 Chunk type: {type(chunk).__name__}")
            print(
                f"📦 Chunk attributes: {dir(chunk) if hasattr(chunk, '__dict__') else 'N/A'}"
            )

            # Try different ways to extract text
            text = None
            if hasattr(chunk, "data"):
                text = chunk.data
            elif hasattr(chunk, "delta"):
                if hasattr(chunk.delta, "text"):
                    text = chunk.delta.text
                elif isinstance(chunk.delta, dict) and "text" in chunk.delta:
                    text = chunk.delta["text"]
            elif isinstance(chunk, str):
                text = chunk
            elif isinstance(chunk, dict) and "data" in chunk:
                text = chunk["data"]

            if text:
                print(f"📤 Yielding: {text[:100]}...")
                yield text
            else:
                print(f"⚠️  No text found in chunk: {chunk}")
    except Exception as e:
        print(f"❌ Streaming error: {e}")
        import traceback

        traceback.print_exc()
        yield f"Error: {str(e)}"
 

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    """
    Application startup routine.
    
    Initializes and runs the Bedrock Agent Core application server,
    making the supervisor agent available for request processing.
    """
    app.run()
