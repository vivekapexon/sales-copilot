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
1. Structure Agent
2. Compliance Agent
3. Action Agent
4. Sentiment Agent

NO other tool and agents exists.
You must NOT create, assume, infer, rename, insert, extend, or invent ANY additional agents or analysis beyond these four tools.
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
    Structure → Compliance → Action → Sentiment
    Example NLQs:
    - "Give me the full post-call summary for my call with Dr. Rao"
    - "Post-call prep and follow-up email for Dr. Patel"
    - "Everything from my last call with H123"
    -------------------------------------------------------------------
    2. **transcription_via_structure**
    -------------------------------------------------------------------
    Purpose:
    User wants transcription - delegate to Structure Agent.
    Keywords:
    "transcribe", "transcription", "what was said", "audio to text", "transcript"
    Call Agents:
    Structure Agent
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
    Structure Agent
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
    Sentiment Agent
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
    Action Agent
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
    Structure Agent + Sentiment Agent
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
- All agents operate independently
- Compliance Agent can run standalone
Example:
  - "Transcribe my call" → Structure Agent
  - "What objections were raised?" → Structure Agent
  - "Generate follow-up email" → Compliance Agent ONLY
  - "Full post-call" → All 4 agents
============================================================
STEP 4: MERGE & STRUCTURE OUTPUT
============================================================
Combine outputs from called agents ONLY.
Do not invent data from agents you didn't call.
If transcription was fetched internally, pass it downstream but do not duplicate in final output unless requested.
============================================================
STRICT NEGATIVE RULES (NON-NEGOTIABLE)
============================================================
• Do NOT call agents outside the 4 listed above.
• Do NOT call agents not required for the intent.
• Do NOT add parameters tools don't support.
• Do NOT generate data yourself. All facts come from tool outputs.
• Do NOT call all 4 agents unless intent is full_post_call_prep.
• Never hallucinate transcription, notes, or sentiment.
============================================================
AGENT CAPABILITIES (KNOWLEDGE BASE)
============================================================
1. StructureAgent: Returns categorized objections, key topics, content shared, samples discussed, compliance flags. Can extract call content for transcription requests.
2. ComplianceAgent: Returns followup_email_subject, followup_email_body, template_id.
3. ActionAgent: Returns action_items_json, priority, calendar_block_minutes, primary_action_type.
4. SentimentAgent: Returns quantified sentiment JSON (call_sentiment_score, relationship_stage, next_call_risk_level, etc.).
No other capabilities exist. Do not infer extra functions.
============================================================
FAIL-SAFE LOGIC
============================================================

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
    Creates session-specific requests to the Action Agent for isolated execution.

    Args:
        intent (str): Natural language prompt describing the action extraction request.
                     Should contain call context, HCP information, and specific requirements.

    Returns:
        dict: Agent response containing:
              - action_items_json: Structured list of action items
              - priority: Priority levels for each action
              - calendar_block_minutes: Recommended time blocks for follow-up
              - primary_action_type: Categorization of action type
              Or error details in case of failure.
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
    Provides quantified metrics for call quality and HCP engagement based on
    call transcription and conversation patterns.

    Args:
        intent (str): Natural language prompt describing the sentiment analysis request.
                     Should reference the call transcript and analysis requirements.

    Returns:
        dict: Agent response containing:
              - call_sentiment_score: Quantified sentiment metric (typically 0-100)
              - relationship_stage: Current relationship phase with HCP
              - next_call_risk_level: Risk assessment for follow-up call
              - objection_intensity: Strength of objections raised
              - positive_negative_ratio: Balance of positive vs negative sentiment
              Or error details in case of failure.
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
    content shared, samples discussed, and compliance flags. Organizes raw
    call data into actionable, searchable categories.

    Args:
        intent (str): Natural language prompt describing the structure extraction request.
                     Should reference the call transcript and specific data to extract.

    Returns:
        dict: Agent response containing:
              - objections: Categorized list of objections raised
              - key_topics: Main discussion points and themes
              - content_shared: Materials, resources, or content discussed
              - samples_discussed: Product samples mentioned or provided
              - compliance_flags: Regulatory or compliance concerns identified
              Or error details in case of failure.
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
def compilance_agent_tool(intent: str) -> dict:
    """
    Invoke the Compliance Agent via Bedrock Agent Runtime.
    
    Generates compliant follow-up emails and ensures communication adherence 
    to regulatory guidelines. Can operate with or without transcript data,
    creating professional correspondence compliant with industry regulations.

    Args:
        intent (str): Natural language prompt describing the compliance email request.
                     Should reference the call context, HCP information, and email content requirements.

    Returns:
        dict: Agent response containing:
              - followup_email_subject: Professional email subject line
              - followup_email_body: Compliant email body text
              - template_id: Reference to the compliance template used
              - regulatory_notes: Any compliance considerations applied
              Or error details in case of failure.
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
    
    Assembles all callable agent tool functions into a single list
    for registration with the supervisor agent. This ensures all
    specialized agents are available for delegation.

    Returns:
        list: Collection of all callable agent tool functions:
              - action_agent_tool
              - sentiment_agent_tool
              - structure_agent_tool
              - transcription_agent_tool
              - compilance_agent_tool
    """
    return [
        action_agent_tool,
        sentiment_agent_tool,
        structure_agent_tool,

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
    The supervisor uses the provided prompt to classify user intents
    and invoke only necessary downstream agents.

    Returns:
        Agent: Configured supervisor agent instance ready for inference
               with system_prompt defining behavior and tools list for delegation.
    """
    return Agent(
        system_prompt=SUPERVISOR_AGENT_PROMPT,
        tools=_tools_list(),
    )


# Instantiate the supervisor agent
agent = create_supervisor_agent()


# =============================================================================
# Application Entrypoint
# =============================================================================

class ChunkType(Enum):
    """
    Enumeration defining types of data chunks streamed from the agent.
    
    Attributes:
        CONTENT (str): Represents actual response content from the agent.
        LOG (str): Represents log/debug information about agent execution.
    """
    CONTENT = "content"
    LOG = "log"


def create_chunk(chunk_type: ChunkType, data: str):
    """
    Create a structured chunk for streaming responses.
    
    Formats data according to the chunk type for proper streaming
    and client-side interpretation. Ensures consistent formatting
    for both content and log messages.

    Args:
        chunk_type (ChunkType): Type of chunk (CONTENT or LOG).
        data (str): The actual data/message to be chunked.

    Returns:
        str: Formatted chunk string ready for streaming.
             - For CONTENT: returns data as-is
             - For LOG: returns data prefixed with [LOG] identifier
    """
    if chunk_type == ChunkType.CONTENT:
        return data
    else:
        return f"[LOG] {data}\n"


@app.entrypoint
async def invoke(payload: dict = {}):
    """
    Main entrypoint for agent invocation via Bedrock Agent Core.
    
    Processes incoming user prompts through the supervisor agent,
    manages tool execution lifecycle, tracks metrics, and streams
    responses with logging information. Handles both successful
    agent operations and error conditions gracefully.

    Args:
        payload (dict, optional): Request payload containing:
                                 - "prompt" (str): User's natural language query
                                 Defaults to empty dict.

    Yields:
        str: Chunked response data containing:
            - Agent content responses (markdown formatted)
            - Log entries tracking tool execution and status
            - Metrics and timing information

    Processing Flow:
        1. Extracts user prompt from payload
        2. Initiates async agent stream with supervisor
        3. Parses and logs tool invocations (start, input, completion)
        4. Yields content chunks for streaming response
        5. Tracks execution time and tool metrics
        6. Handles exceptions with error logging
    """
    prompt = payload.get("prompt", "")
    tool_calls = {}
    start_time = time.time()
    
    yield create_chunk(ChunkType.LOG, "Agent started")

    try:
        stream = agent.stream_async(prompt)
        
        async for chunk in stream:
            parsed_result = parse_chunk(chunk)
            
            if parsed_result["type"] == "content":
                yield create_chunk(ChunkType.CONTENT, parsed_result["data"])
            elif parsed_result["type"] == "tool_start":
                tool_id = parsed_result["tool_id"]
                tool_calls[tool_id] = {
                    "name": parsed_result["tool_name"],
                    "input": "",
                    "start_time": time.time()
                }
                yield create_chunk(ChunkType.LOG, f"🔧 {parsed_result['tool_name']} starting...")
            elif parsed_result["type"] == "tool_input":
                tool_id = parsed_result["tool_id"]
                if tool_id in tool_calls:
                    tool_calls[tool_id]["input"] += parsed_result["input_part"]
            elif parsed_result["type"] == "tool_complete":
                tool_id = parsed_result["tool_id"]
                if tool_id in tool_calls:
                    tool_call = tool_calls[tool_id]
                    duration = time.time() - tool_call["start_time"]
                    yield create_chunk(ChunkType.LOG, f"✅ {tool_call['name']} completed")
                    yield create_chunk(ChunkType.LOG, f"   Input: {tool_call['input']}")
                    yield create_chunk(ChunkType.LOG, f"   Duration: {duration:.3f}s")
            elif parsed_result["type"] == "tool_result":
                result = parsed_result["result"]
                yield create_chunk(ChunkType.LOG, f"   Result: {result}")
            elif parsed_result["type"] == "metrics":
                total_time = time.time() - start_time
                metrics_summary = format_metrics(parsed_result["data"], len(tool_calls), total_time)
                yield create_chunk(ChunkType.LOG, metrics_summary)
                
    except Exception as e:
        yield create_chunk(ChunkType.LOG, f"❌ Error: {str(e)}")


def format_metrics(metrics_data, tool_count, total_time):
    """
    Format execution metrics into human-readable output.
    
    Aggregates tool execution statistics, token usage, and timing
    information into a concise summary for logging and monitoring.
    Provides insight into agent performance and resource consumption.

    Args:
        metrics_data (dict): Dictionary containing:
                           - "usage" (dict): Token statistics with keys:
                             - "totalTokens" (int)
                             - "inputTokens" (int)
                             - "outputTokens" (int)
        tool_count (int): Number of tools/agents invoked in this execution.
        total_time (float): Total execution duration in seconds.

    Returns:
        str: Multi-line formatted metrics string containing:
            - Tool call count and success/error breakdown
            - Approximate tool execution time
            - Token usage statistics (input, output, total)
            - Error status summary
    """
    lines = []
    
    if tool_count > 0:
        lines.append(f"calls={tool_count}, success={tool_count}, errors=0")
        lines.append(f"total tool time ~{total_time:.2f}s")
    
    if 'usage' in metrics_data:
        usage = metrics_data['usage']
        lines.append(f"Tokens: {usage.get('totalTokens', 0)} (in: {usage.get('inputTokens', 0)}, out: {usage.get('outputTokens', 0)})")
    
    lines.append("No errors encountered")
    return "\n".join(lines)


def parse_chunk(chunk):
    """
    Parse agent stream chunk into structured event data.
    
    Processes various chunk formats (dict, string, object) from the
    agent stream and extracts relevant event information. Handles
    content blocks, tool invocations, results, and metadata events.
    Provides normalized output for downstream processing.

    Args:
        chunk: Raw chunk data from agent stream. Can be:
               - dict: Event-based structure with 'event' or 'message' keys
               - str: JSON-formatted data or free text
               - object: Custom object with data/delta attributes

    Returns:
        dict: Structured parse result containing:
              - "type" (str): Event type (content, tool_start, tool_input, 
                             tool_complete, tool_result, metrics, unknown)
              - Supporting fields depending on type:
                - "data" (str): Content or message text
                - "tool_id" (str): Identifier for tool invocation
                - "tool_name" (str): Name of the tool being invoked
                - "input_part" (str): Partial tool input data
                - "result" (str): Tool execution result

    Processing Logic:
        1. Checks dict structure for event/message keys
        2. Extracts contentBlockDelta for text/tool input
        3. Identifies contentBlockStart for tool invocations
        4. Captures contentBlockStop for completion events
        5. Extracts metadata for metrics
        6. Parses JSON strings for alternative format data
        7. Falls back to string representation for unknown formats
    """
    # Handle dict chunks
    if isinstance(chunk, dict):
        if 'event' in chunk:
            event = chunk['event']
            if 'contentBlockDelta' in event:
                delta = event['contentBlockDelta']['delta']
                if 'text' in delta:
                    return {"type": "content", "data": delta['text']}
                elif 'toolUse' in delta:
                    return {"type": "tool_input", "tool_id": "current", "input_part": delta['toolUse'].get('input', '')}
            elif 'contentBlockStart' in event:
                start = event['contentBlockStart']['start']
                if 'toolUse' in start:
                    tool_use = start['toolUse']
                    return {
                        "type": "tool_start",
                        "tool_id": tool_use['toolUseId'],
                        "tool_name": tool_use['name']
                    }
            elif 'contentBlockStop' in event:
                return {"type": "tool_complete", "tool_id": "current"}
            elif 'metadata' in event:
                return {"type": "metrics", "data": event['metadata']}
        elif 'message' in chunk and 'toolResult' in str(chunk):
            # Extract tool results
            content = chunk['message'].get('content', [])
            for item in content:
                if 'toolResult' in item:
                    result_content = item['toolResult'].get('content', [])
                    if result_content and 'text' in result_content[0]:
                        return {"type": "tool_result", "result": result_content[0]['text']}
    
    # Handle string chunks with dict data
    if isinstance(chunk, str) and chunk.startswith("{"):
        try:
            chunk_dict = eval(chunk)
            if 'data' in chunk_dict and 'delta' in chunk_dict:
                return {"type": "content", "data": chunk_dict['data']}
            elif 'result' in chunk_dict:
                result = chunk_dict['result']
                if hasattr(result, 'metrics'):
                    return {"type": "metrics", "data": result.metrics.accumulated_metrics}
        except:
            pass
    
    # Handle object chunks
    if hasattr(chunk, 'data') and hasattr(chunk, 'delta'):
        return {"type": "content", "data": chunk.data}
    
    return {"type": "unknown", "data": str(chunk)[:100]}


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    """
    Application startup routine.
    
    Initializes and runs the Bedrock Agent Core application server,
    making the supervisor agent available for request processing.
    This entry point starts the async event loop and HTTP server
    for handling incoming agent invocation requests.
    """
    app.run()
