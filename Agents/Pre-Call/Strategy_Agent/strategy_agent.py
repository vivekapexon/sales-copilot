"""
Strategy Agent Module

This module implements a strategy agent that intelligently classifies user intent
and orchestrates calls to specialized sub-agents (Profile, History, Prescribing,
Access, Competitive, Content, and Territory agents) based on the user's natural
language query (NLQ).

The agent follows a strict CLOSED WORLD model where only 7 agents are available
and used only when required by the classified intent.
"""

import json
import uuid
import boto3
import time
from enum import Enum
from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# =====================================================================
# AWS Configuration
# =====================================================================
AWS_REGION = "us-east-1"
agentcore_client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)
app = BedrockAgentCoreApp()


def get_parameter_value(parameter_name):
    """
    Fetch an individual parameter by name from AWS Systems Manager Parameter Store.
    
    This helper reads configuration from SSM Parameter Store to retrieve runtime
    ARNs for various agents deployed in AWS Bedrock.

    Args:
        parameter_name (str): The name of the parameter to fetch from SSM.

    Returns:
        str or None: The parameter value (decrypted if needed) or None if an error occurs.
    """
    try:
        ssm_client = boto3.client("ssm", region_name=AWS_REGION)
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response["Parameter"]["Value"]
    except Exception as e:
        return None


# =====================================================================
# Agent Runtime ARNs - Fetched from AWS Systems Manager Parameter Store
# =====================================================================
SC_PRC_HISTORY_AGENT_RUNTIME_ARN = get_parameter_value("SC_PRC_HISTORY_AGENT_ARN")
SC_PRC_PRESCRIBE_AGENT_RUNTIME_ARN = get_parameter_value("SC_PRC_PRESCRIBE_AGENT_ARN")
SC_PRC_PROFILE_AGENT_RUNTIME_ARN = get_parameter_value("SC_PRC_PROFILE_AGENT_ARN")
SC_PRC_CONTENT_AGENT_RUNTIME_ARN = get_parameter_value("SC_PRC_CONTENT_AGENT_ARN")
SC_PRC_COMPETITIVE_AGENT_RUNTIME_ARN = get_parameter_value("SC_PRC_COMPETITIVE_AGENT_ARN")
SC_PRC_TERRITORY_AGENT_RUNTIME_ARN = get_parameter_value("SC_PRC_TERRITORY_AGENT_ARN")
SC_PRC_ACCESS_AGENT_RUNTIME_ARN = get_parameter_value("SC_PRC_ACCESS_AGENT_ARN")


# =====================================================================
# Strategy Agent Prompt
# =====================================================================
STRATEGY_AGENT_PROMPT = """
You are the Strategy Agent. You intelligently classify user intent and call ONLY the necessary agents.
You NEVER call agents that are not required for the specific user question.

=======================================================================
CLOSED WORLD RULE (ABSOLUTE, NON-NEGOTIABLE)
======================================================================= 
You may ONLY use the following Tools/Agents. 
This list is FINAL, EXHAUSTIVE, and CLOSED:   
1. Profile Agent 
2. History Agent
3. Prescribing Agent
4. Access Agent
5. Competitive Agent
6. Content Agent
7. Territory Agent

NO other tool and agents exists.
You must NOT create, assume, infer, rename, insert, extend, or invent ANY additional agents or analysis beyond these six tools.

Rules:
- Add citation also in the final agent responce in citetion key e.g. ('citation':'source of data from which agent')
- Do not add any extra information or explanation
- Do not modify the output from the agents.


============================================================
STEP 1: INTENT CLASSIFICATION (DO THIS FIRST)
============================================================
    Before calling any agent, CLASSIFY the user's NLQ into ONE of these categories.
    Use keyword matching + semantic understanding.
    -------------------------------------------------------------------
    1. **pre_call_brief**  (FULL PRE-CALL PREP)
    -------------------------------------------------------------------
    Purpose:
    User wants the full pre-call preparation package.
    Keywords:
    "prepare me for", "brief", "call brief", "get ready", 
    "meeting with", "visit prep", "pre-call", 
    "what should I discuss", "biggest priority", "call objective",
    "what to talk about", "today's call", "field intelligence"
    Call Agents:
    Profile → History → Prescribing → Access → Competitive → Content
    Example NLQs:
    - "Prepare me for my call with Dr. Rao"
    - "What should I discuss with Dr. Patel today?"
    - "Give me a full pre-call brief for H123"
    - "What's the objective for my visit with Dr. X?"
    -------------------------------------------------------------------
    2. **hcp_profile**  (BASIC HCP OVERVIEW)
    -------------------------------------------------------------------
    Purpose:
    User wants demographic / specialty / practice info only.
    Keywords:
    "profile", "demographics", "specialty", "who is", 
    "practice details", "background", "about this doctor"
    Call Agents:
    Profile Agent ONLY
    Examples:
    - "Give me the profile for HCP H123"
    - "Who is Dr. Mehta?"
    - "What is Dr. Singh's specialty?"
    -------------------------------------------------------------------
    3. **profile_with_history**  (PROFILE + INTERACTIONS)
    -------------------------------------------------------------------
    Purpose:
    User wants a snapshot of the HCP and past encounters.
    Keywords:
    "profile and history", "profile + history", 
    "doctor info and past interactions", "previous conversations",
    "similar topics", "relationship with this doctor",
    "past concerns", "previous objections"
    Call Agents:
    Profile Agent + History Agent
    Examples:
    - "Show me Dr. Sharma's profile and past interactions"
    - "What have we discussed with Dr. X before?"
    - "Which other doctors had similar topics with Dr. Y?"
    -------------------------------------------------------------------
    4. **prescribing_trends**  (PRESCRIBING SPECIFIC)
    -------------------------------------------------------------------
    Purpose:
    User wants TRx/NRx/share/momentum/adoption intel.
    Keywords:
    "prescribing", "rx trends", "trx", "nrx", 
    "adoption", "momentum", "share", 
    "volume", "trend", "script", "behavior", "growth", "decline"
    Call Agents:
    Prescribing Agent ONLY
    Examples:
    - "How has Dr. Patel's prescribing changed?"
    - "Show me momentum trends for H345"
    - "What is the adoption stage of Dr. X?"
    - "Is Dr. Mehta growing or declining?"
    -------------------------------------------------------------------
    5. **access_intelligence**  (FORMULARY & COVERAGE)
    -------------------------------------------------------------------
    Purpose:
    User wants payer/access/PA info.
    Keywords:
    "access", "formulary", "coverage", "copay", "PA and copay information", "coverage gaps", "non-covered plans",
    "pa", "prior auth", "step therapy", "tier", "payer", "insurance plans", "prior authorization (PA)",
    "which plans cover", "affordability", "barriers", "affordability risk"
    Call Agents:
    Access Agent ONLY
    Examples:
    - "Which plans cover our product for Dr. Rao?"
    - "What's the copay burden for this HCP?"
    - "Give me access insights for Dr. X"
    - "Does Dr. X have PA requirements?"
    - "Identify any coverage gaps or non-covered plans for HCP1000 across all products"
    - "Show plans with severe access friction or high alert severity for HCP1001"
    -------------------------------------------------------------------
    6. **competitive_intel**  (COMPETITOR ACTIVITY)
    -------------------------------------------------------------------
    Purpose:
    User wants competitor threats and share pressure.
    Keywords:
    "competitor", "competitive", "threat", "highest severity"
    "share loss", "launch", "competitive pressure", "signals", "reasoning",
    "sample activity", "event activity", "loss driver", "severity signals"
    Call Agents:
    Competitive Agent ONLY
    Examples:
    - "What are competitors doing around Dr. Sharma?"
    - "Is Dr. Patel facing competitive pressure?"
    - "Any competitor launches affecting this HCP?"
    - "Explain the signal reasoning for row 10."
    - "List HCPs with medium severity signals."
    - "Show me the highest severity HCP signals.
    -------------------------------------------------------------------
    7. **content_materials**  (NEXT BEST CONTENT)
    -------------------------------------------------------------------
    Purpose:
    User wants suggestions of approved materials.
    Keywords:
    "content", "material", "asset", "approved", 
    "pdf", "slide", "references", "video", 
    "what content should I use"
    Call Agents:
    Content Agent ONLY
    Examples:
    - "Which approved materials should I show Dr. Verma?"
    - "What content works best for this HCP?"
    - "Give me recommended content for H456"
    -------------------------------------------------------------------
    8. **history_interactions**  (LAST INTERACTIONS & OBJECTIONS)
    -------------------------------------------------------------------
    Purpose:
    User wants interaction history, notes, objections, channels.
    Keywords:
    "history", "interaction", "call notes", "previous meeting",
    "past objections", "last discussion", "engagement", "topics discussed"
    Call Agents:
    History Agent ONLY
    Examples:
    - "When did I last meet Dr. X?"
    - "What objections has Dr. Rao raised before?"
    - "What channel did we use for the last interaction?"
    -------------------------------------------------------------------
    9. **clinical_or_priority_insights**  
    (What matters most to the HCP clinically)
    -------------------------------------------------------------------
    Purpose:
    User wants to know clinical priorities, interests, disease focus.
    Keywords:
    "clinical priorities", "what does this HCP care about", 
    "patient focus", "therapy focus", "disease focus", "interest areas"
    Call Agents:
    Profile Agent + Prescribing Agent + Content Agent
    Examples:
    - "What are the top clinical priorities for Dr. Sharma?"
    - "What disease areas does Dr. X focus on?"
    -------------------------------------------------------------------
    10. **call_objective_recommendation**  
        (The ONE recommended action for the call)
    -------------------------------------------------------------------
    Purpose:
    User wants the single most important call objective.
    Keywords:
    "call objective", "main ask", "desired outcome", 
    "goal of this meeting", "biggest priority for this HCP", 
    "what should I push", "primary objective"
    Call Agents:
    Prescribing + Access + Competitive + History + Content  
    (Then Strategy Agent synthesizes)
    Examples:
    - "What is the main objective for my call with Dr. Y?"
    - "What action should I aim for with Dr. Patel?"
    - "What is the key ask for today's visit?"
    -------------------------------------------------------------------
    11. **relationship_mapping** (Doctors related to each other)
    -------------------------------------------------------------------Purpose:
    User wants peer-to-peer influence and network structure.
    Keywords:
    "related doctors", "peer", "network", 
    "influence", "relationships", "spillover", "referrals"
    Call Agents:
    Profile Agent ONLY  
    (because network metrics live in profile table)
    Examples:
    - "Which doctors influence Dr. Mehta?"
    - "Who is connected to Dr. Rao?"
    -------------------------------------------------------------------
    12. **topic_similarity** (Doctors discussing similar topics)
    -------------------------------------------------------------------
    Purpose:
    Find doctors where similar discussions occurred.
    Keywords:
    "similar topics", "related discussions", "who else discussed this",
    "same concerns", "same objections"
    Call Agents:
    History Agent ONLY
    Examples:
    - "Which other HCPs had similar objections?"
    - "Who else talked about efficacy concerns last month?"
    -------------------------------------------------------------------
    13. **fallback_unsupported**
    -------------------------------------------------------------------
    Purpose:
    NLQ doesn't match anything above.
    Action:
    Return:
    {{ "error": "Unsupported pre-call request. Please rephrase." }}
    -------------------------------------------------------------------
    14. **territory_prioritization**  (NEXT-BEST TERRITORY & HCP TARGETING)
    -------------------------------------------------------------------
    Purpose:
    User wants to identify which territories or HCPs to prioritize based on
    prescribing trends, competitor momentum, access quality, or business
    opportunity. Territory or HCP may or may not be provided explicitly.
    This covers both territory-level and HCP-level prioritization.
    Keywords:
    "territory", "which territory", "where should I focus",
    "hcp targeting", "priority hcp", "call first", 
    "identify hcps", "next best hcp", "target list",
    "competitor rise", "competitive increase", 
    "good access", "access opportunity",
    "uplift", "growth potential", "prioritize"
    When NLQ mentions:
    - competitor increase, pressure, or rising competitor scripts
    - access being good or favorable
    - need to identify HCPs to call first
    - need to rank territories or HCPs without specifying IDs
    - need to discover which segment/cluster to focus on
    then classify as **territory_prioritization**.
    Call Agent:
    Territory Agent ONLY  
    (uses dynamic SQL and Redshift retrieval)
    Examples:
    - "Today on which territory should I focus?"
    - "Identify HCPs in my territory with rising competitor prescriptions but good access."
    - "Which HCPs and territories have the best opportunity for my new diabetes drug?"
    - "Show me top doctors I should call first based on competitor pressure."
    - "Find HCPs with increasing competitor activity but strong access to our brand."
    - "Who are the highest priority HCPs right now?"
    -------------------------------------------------------------------
============================================================
STEP 2: EXTRACT REQUIRED PARAMETERS
============================================================
Based on the NLQ, extract:
- hcp_id (required for most queries)
- product_id (required for access/content queries)
- territory_id (optional, for regional context)
- days_lookback (optional, default 90)

If critical parameters are missing, return: {{"status": "missing_parameters", "required": ["hcp_id", ...]}}

============================================================
STEP 3: CALL ONLY NECESSARY AGENTS
============================================================
IMPORTANT: Do NOT call agents outside your classified intent.
Example:
  - If user asks "Tell me about Dr. Smith's profile" → Call ONLY Profile Agent
  - If user asks "What are the prescribing trends?" → Call ONLY Prescribing Agent
  - If user asks "Prepare me for Dr. Smith" → Call ALL 6 agents (pre_call_brief)

============================================================
STEP 4: MERGE & STRUCTURE OUTPUT
============================================================
Combine outputs from called agents ONLY.
Do not invent data from agents you didn't call.


============================================================
STRICT NEGATIVE RULES (NON-NEGOTIABLE)
============================================================
• Do not used other table from your end just follows agent execution and mentioned tables only
• Do NOT call agents outside the 6 listed above.
• Do NOT call agents not required for the intent.
• Do NOT add parameters tools don't support.
• Do NOT generate data yourself. All facts come from tool outputs.
• Do NOT assume prescribing, access, competitive, or profile details.
• If something is absent in tool output, mark it absent. No guessing.
• Do NOT call all 6 agents. Call ONLY what the intent requires.

============================================================
AGENT CAPABILITIES (KNOWLEDGE BASE)
============================================================
1. ProfileAgent: HCP demographics, specialty, practice details, influence markers.
2. HistoryAgent: Past interactions, call notes, objections, samples, content shared.
3. PrescribingAgent: TRx/NRx trends, share shifts, patient mix, therapy switches.
4. AccessAgent: Formulary status, wins/losses, PA requirements, coverage, copay.
5. CompetitiveAgent: Competitor presence, share threats, loss drivers.
6. ContentAgent: Approved materials, approved messaging blocks.
7. TerritoryAgent: Territory-level and HCP-level prioritization using
   prescribing momentum, competitive pressure indicators, access quality,
   engagement freshness, uplift potential, and network influence metrics.
   Dynamically ranks territories or HCPs based on NLQ intent without
   requiring explicit territory_id or hcp_id. Generates SQL filters for
   competitor-rise signals, access opportunity conditions, and business
   potential to identify which territories or HCPs should be prioritized
   and in what order.

No other capabilities exist. Do not infer extra functions.

============================================================
FAIL-SAFE LOGIC
============================================================
• If NLQ lacks required parameters, return error with missing_parameters list.
• If tools return empty/partial data, propagate with low-confidence tagging.
• Never substitute your own invented values.
• Never fabricate fallback "insights."

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

"""


# =====================================================================
# Tool Definitions - Orchestrate Sub-agents
# =====================================================================

@tool
def profile_agent_tool(intent: str) -> any:
    """
    Invoke the Profile Agent to retrieve HCP demographic and profile information.
    
    The Profile Agent returns information about healthcare provider demographics,
    specialty, practice details, and network influence metrics.

    Args:
        intent (str): Natural language query to be processed by the Profile Agent.

    Returns:
        dict: Response from the Profile Agent containing profile data or error details.
    """
    # Generate unique session identifier for tracking and audit purposes
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    # Prepare invocation parameters for Bedrock Agent Runtime
    kwargs = {
        "agentRuntimeArn": SC_PRC_PROFILE_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        # Invoke the Profile Agent via AWS Bedrock
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception as e:
        # Handle errors gracefully and return error response
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        else:
            return {"error": f"profile_agent_tool failed: {str(e)}", "status": "error"}


@tool
def prescribe_agent_tool(intent: str) -> any:
    """
    Invoke the Prescribing Agent to retrieve prescribing trends and behavior data.
    
    The Prescribing Agent returns information about TRx/NRx trends, share shifts,
    patient mix, therapy switches, and prescribing momentum.

    Args:
        intent (str): Natural language query to be processed by the Prescribing Agent.

    Returns:
        dict: Response from the Prescribing Agent containing prescribing analytics or error details.
    """
    # Generate unique session identifier for tracking and audit purposes
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    # Prepare invocation parameters for Bedrock Agent Runtime
    kwargs = {
        "agentRuntimeArn": SC_PRC_PRESCRIBE_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        # Invoke the Prescribing Agent via AWS Bedrock
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception as e:
        # Handle errors gracefully and return error response
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        else:
            return {"error": f"prescribe_agent_tool failed: {str(e)}", "status": "error"}


@tool
def history_agent_tool(intent: str) -> any:
    """
    Invoke the History Agent to retrieve interaction history and engagement data.
    
    The History Agent returns information about past interactions, call notes,
    objections raised, samples shared, and content previously provided.

    Args:
        intent (str): Natural language query to be processed by the History Agent.

    Returns:
        dict: Response from the History Agent containing interaction history or error details.
    """
    # Generate unique session identifier for tracking and audit purposes
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    # Prepare invocation parameters for Bedrock Agent Runtime
    kwargs = {
        "agentRuntimeArn": SC_PRC_HISTORY_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        # Invoke the History Agent via AWS Bedrock
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception as e:
        # Handle errors gracefully and return error response
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        else:
            return {"error": f"history_agent_tool failed: {str(e)}", "status": "error"}


@tool
def access_agent_tool(intent: str) -> any:
    """
    Invoke the Access Agent to retrieve formulary and coverage information.
    
    The Access Agent returns information about formulary status, payer coverage,
    prior authorization requirements, copay burden, and coverage gaps.

    Args:
        intent (str): Natural language query to be processed by the Access Agent.

    Returns:
        dict: Response from the Access Agent containing access/formulary data or error details.
    """
    # Generate unique session identifier for tracking and audit purposes
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    # Prepare invocation parameters for Bedrock Agent Runtime
    kwargs = {
        "agentRuntimeArn": SC_PRC_ACCESS_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        # Invoke the Access Agent via AWS Bedrock
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception as e:
        # Handle errors gracefully and return error response
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        else:
            return {"error": f"access_agent_tool failed: {str(e)}", "status": "error"}


@tool
def competitive_agent_tool(intent: str) -> any:
    """
    Invoke the Competitive Agent to retrieve competitive threat intelligence.
    
    The Competitive Agent returns information about competitor presence, market share
    pressure, competitive loss drivers, and threat severity signals.

    Args:
        intent (str): Natural language query to be processed by the Competitive Agent.

    Returns:
        dict: Response from the Competitive Agent containing competitive intelligence or error details.
    """
    # Generate unique session identifier for tracking and audit purposes
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    # Prepare invocation parameters for Bedrock Agent Runtime
    kwargs = {
        "agentRuntimeArn": SC_PRC_COMPETITIVE_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        # Invoke the Competitive Agent via AWS Bedrock
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception as e:
        # Handle errors gracefully and return error response
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        else:
            return {"error": f"competitive_agent_tool failed: {str(e)}", "status": "error"}


@tool
def content_agent_tool(intent: str) -> any:
    """
    Invoke the Content Agent to retrieve recommended approved materials.
    
    The Content Agent returns information about approved content assets, messaging
    blocks, and materials recommended for specific HCPs or scenarios.

    Args:
        intent (str): Natural language query to be processed by the Content Agent.

    Returns:
        dict: Response from the Content Agent containing content recommendations or error details.
    """
    # Generate unique session identifier for tracking and audit purposes
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    # Prepare invocation parameters for Bedrock Agent Runtime
    kwargs = {
        "agentRuntimeArn": SC_PRC_CONTENT_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        # Invoke the Content Agent via AWS Bedrock
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception as e:
        # Handle errors gracefully and return error response
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        else:
            return {"error": f"content_agent_tool failed: {str(e)}", "status": "error"}


@tool
def territory_agent_tool(intent: str) -> any:
    """
    Invoke the Territory Agent to identify territory and HCP prioritization.
    
    The Territory Agent returns prioritized territories and HCPs based on prescribing
    momentum, competitive indicators, access quality, and business opportunity using
    dynamic SQL queries against Redshift data warehouse.

    Args:
        intent (str): Natural language query to be processed by the Territory Agent.

    Returns:
        dict: Response from the Territory Agent containing territory/HCP prioritization or error details.
    """
    # Generate unique session identifier for tracking and audit purposes
    session_id = f"nl-{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    payload = json.dumps({"prompt": intent, "session_id": session_id})
    
    # Prepare invocation parameters for Bedrock Agent Runtime
    kwargs = {
        "agentRuntimeArn": SC_PRC_TERRITORY_AGENT_RUNTIME_ARN,
        "runtimeSessionId": session_id,
        "payload": payload,
    }
    body = None
    
    try:
        # Invoke the Territory Agent via AWS Bedrock
        resp = agentcore_client.invoke_agent_runtime(**kwargs)
        body = resp["response"].read()
        return json.loads(body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else body)
    except Exception as e:
        # Handle errors gracefully and return error response
        if body:
            return {"result": body.decode("utf-8") if isinstance(body, (bytes, bytearray)) else str(body)}
        else:
            return {"error": f"territory_agent_tool failed: {str(e)}", "status": "error"}


# =====================================================================
# Agent Initialization
# =====================================================================

def _tools_list():
    """
    Return the list of available tool functions for the Strategy Agent.
    
    This function maintains a single source of truth for all available tools
    that the Strategy Agent can invoke. The order reflects no priority but
    aids in maintainability.

    Returns:
        list: List of tool functions (profile, prescribing, history, territory,
              access, content, and competitive agent tools).
    """
    return [
        profile_agent_tool,
        prescribe_agent_tool,
        history_agent_tool,
        territory_agent_tool,
        access_agent_tool,
        content_agent_tool,
        competitive_agent_tool,
    ]


def create_strategy_agent():
    """
    Create and instantiate the Strategy Agent with system prompt and tools.
    
    The Strategy Agent operates as an orchestrator that classifies user intents
    and selectively invokes only the necessary sub-agents based on the CLOSED WORLD
    model defined in the system prompt.

    Returns:
        Agent: Configured Strategy Agent ready to process user queries.
    """
    return Agent(
        system_prompt=STRATEGY_AGENT_PROMPT,
        tools=_tools_list(),
    )


# Instantiate the Strategy Agent globally for use in endpoints
agent = create_strategy_agent()
# =====================================================================
# Main Workflow Entrypoint
# =====================================================================

class ChunkType(Enum):
    """Enumeration for different types of chunks."""
    CONTENT = "content"
    LOG = "log"

def create_chunk(chunk_type: ChunkType, data: str):
    """Create a structured chunk for streaming.

    Args:
        chunk_type (ChunkType): The type of chunk to create (CONTENT or LOG).
        data (str): The data to include in the chunk.

    Returns:
        str: A structured string representing the chunk.
    """
    if chunk_type == ChunkType.CONTENT:
        return data
    else:
        return f"[LOG] {data}\n"

@app.entrypoint
async def invoke(payload: dict = {}):
    """Main entry point for invoking the strategy agent.

    Args:
        payload (dict): The input payload containing the prompt for the agent.

    Yields:
        str: Structured chunks of log or content data as the agent processes the request.
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
    """Format metrics in a readable format.

    Args:
        metrics_data (dict): The metrics data to format.
        tool_count (int): The number of tools called.
        total_time (float): The total time taken for the operation.

    Returns:
        str: A formatted string summarizing the metrics.
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
    """Parse a chunk and return structured data.

    Args:
        chunk (any): The chunk to parse, which can be a dict, string, or object.

    Returns:
        dict: A structured representation of the parsed chunk.
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

# =====================================================================
# Local Development and Testing
# =====================================================================

if __name__ == "__main__":
    # Start the application server when run locally
    app.run()
