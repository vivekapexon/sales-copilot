# ---------------------------------------------------------------------------
# SUPERVISOR SYSTEM SUMMARY
# ---------------------------------------------------------------------------
# This module implements a Supervisor Agent that routes any incoming USER QUERY
# to the most appropriate sub-agent based on LLM reasoning and subagents descrption defined in json file under configuration folder.
#
# ✔ The Supervisor prompts a routing LLM (or a stub in debug mode) to return:
#      {
#        reasoning: "...",
#        confidence: 0.xx,
#        calls: [{ agent, input, why, confidence }]
#      }
#
# ✔ Even if the LLM suggests a short or partial 'input' (e.g., "cardiology"),
#   the Supervisor ALWAYS overrides this and passes the FULL ORIGINAL USER QUERY
#   to the selected sub-agent's tool.
#
# ✔ This guarantees consistent sub-agent behavior regardless of LLM output,
#   in both debug mode and real Bedrock production calls.
#
# ✔ In DEBUG_STUB_LLM mode, the stubbed LLM response is also updated to return
#   the full user query as 'input' for easier local testing.
#
# ✔ In production mode, real Bedrock LLM routing is used, but the Supervisor
#   still forces the sub-agent 'input' to the full original user query.
#
# Overall:
# - LLM decides WHICH agent to call.
# - Supervisor decides WHAT input is passed (always the full user query).
# - Sub-agents execute deterministically using the chosen tool and full query.
# ---------------------------------------------------------------------------


import json
from typing import Dict, Any
import boto3
import botocore
import os
from pathlib import Path
from dotenv import load_dotenv
from distutils.util import strtobool

from utilities.logger import logger
from strands import Agent

# ---------------------------------------------------------------------------
# Environment + Global Configuration
# ---------------------------------------------------------------------------
load_dotenv()

DEBUG_STUB_LLM: bool = bool(strtobool(os.getenv("DEBUG_STUB_LLM", "True")))
AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID: str = os.getenv(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20240620-v1:0"
)
BEDROCK_MODEL_CONTENT_TYPE: str = os.getenv("BEDROCK_MODEL_CONTENT_TYPE", "text/plain")
BEDROCK_MODEL_ACCEPT: str = os.getenv("BEDROCK_MODEL_ACCEPT", "application/json")

SUPERVISOR_AGENT_CONFIG_LOCATION: Path = Path(
    os.getenv("SUPERVISOR_AGENT_CONFIG_LOCATION", "configuration/supervisor_agents_config.json")
)

# ---------------------------------------------------------------------------
# Bedrock Client
# ---------------------------------------------------------------------------
def _init_bedrock_client() -> boto3.client: # type: ignore
    """Initialize Bedrock client unless debug stub is active."""
    if DEBUG_STUB_LLM:
        logger.info("DEBUG_STUB_LLM=True → using stubbed LLM responses.")
        return None

    try:
        return boto3.client("bedrock-runtime", region_name=AWS_REGION)
    except Exception as e:
        logger.exception("Failed to create Bedrock client.")
        raise RuntimeError(f"Could not initialize Bedrock client: {e}")

bedrock = _init_bedrock_client()

# ---------------------------------------------------------------------------
# LLM Invocation
# ---------------------------------------------------------------------------
def call_bedrock_llm(prompt: str) -> str: # type: ignore
    """
    Wrapper for LLM calls. Provides a deterministic stub when DEBUG_STUB_LLM=True.
    Production version includes safety, retries, and error logging.
    """
    if DEBUG_STUB_LLM:
        logger.info("Returning deterministic stub response for LLM.")
        return json.dumps({
            "reasoning": "Stub reasoning for debugging",
            "confidence": 0.94,
            "calls": [
                {
                    "agent": "profile_agent",
                    "input": prompt,
                    "why": "Stubbed routing",
                    "confidence": 0.95
                }
            ]
        })

    if bedrock is None:
        raise RuntimeError("Bedrock client was not initialized.")

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 600,
        "temperature": 0.0,
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        logger.debug("Calling Bedrock model.")
        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            accept=BEDROCK_MODEL_ACCEPT,
            contentType="application/json",
            body=json.dumps(payload),
        )

        raw = response["body"].read()
        logger.debug(f"Raw model response: {raw}")

        data = json.loads(raw)
        return data["content"][0]["text"]

    except botocore.exceptions.ClientError as ce: # type: ignore
        logger.exception("AWS ClientError during LLM invocation.")
        raise
    except Exception as e:
        logger.exception("Unexpected error during LLM invocation.")
        raise RuntimeError(f"LLM invocation failed: {e}")


# ---------------------------------------------------------------------------
# Load Subagents
# ---------------------------------------------------------------------------
def load_subagents(path: Path = SUPERVISOR_AGENT_CONFIG_LOCATION) -> Dict[str, Any]:
    """Load agent metadata from JSON configuration."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Subagent config not found at: {path}")
        raise
    except json.JSONDecodeError:
        logger.error("Subagent configuration contains invalid JSON.")
        raise


# ---------------------------------------------------------------------------
# Supervisor Agent
# ---------------------------------------------------------------------------

class SupervisorAgent(Agent):
    """
    Routes USER QUERY → appropriate subagent call(s).
    Enforces strict JSON contract for LLM interactions.
    """
    def __init__(self, subagents: Dict[str, Any]):
        super().__init__(name="SupervisorAgent")
        self.subagents = subagents
        self.instructions = self._supervisor_prompt()   

    def _supervisor_prompt(self) -> str:
        # Clear, strict prompt that requires the LLM to return agents-only and to prefer agents whose
        # 'selection_signals' match the user's query. Includes few-shot examples.
        return (
            """You are the Supervisor Agent. Your job is to decide which subagents should be used to
            satisfy the USER QUERY.
            IMPORTANT GUIDELINES:
            - Use each agent's metadata (especially selection_signals, typical_inputs, and description)
              when deciding which agent(s) to call.
            - Prefer a single, highest-value agent (minimum number of calls). Use more than one agent only if
              the user query legitimately requires multiple distinct capabilities.
            - If selection_signals appear in the USER QUERY, favor agents whose selection_signals best match those phrases.

            CONSTRAINTS (must follow):
            1) RETURN ONLY A SINGLE JSON OBJECT and absolutely no text outside the JSON.
            2) Use the MINIMUM number of calls required to satisfy the request. Prefer 0 or 1 call.
            3) Each call must reference an agent (exact agent name) and MUST NOT include a 'tool' field.
            4) For every call include a short 'why' explaining why that agent is needed and a numeric 'confidence' [0.0-1.0].
            5) Provide an overall routing 'confidence' [0.0-1.0].
            6) If no agent matches the intent, return calls: [] and explain why in 'reasoning'.
            7) If a chosen agent requires an argument, put it as a string in 'input'. If none is needed, use empty string "".

            RETURN SCHEMA EXACTLY (no extra fields):
            {
              reasoning: <text explaining overall routing decision>,
              confidence: <float 0.0-1.0>,
              calls: [
                {
                  agent: <agent_name>,
                  input: <string>,
                  why: <short reason>,
                  confidence: <float 0.0-1.0>
                }
              ]
            }

            AVAILABLE AGENTS AND THEIR METADATA (exact):
            {agents_json}

            FEW-SHOT EXAMPLES (these demonstrate the exact JSON structure you MUST follow and how to use selection_signals):

            Example 1 - direct mapping using selection_signals:
            USER QUERY: "Who is Dr. Jane Doe and what is her specialty? I need a quick profile before my call."
            RATIONALE: The query contains 'who is' and 'profile' which match profile_agent.selection_signals.
            {
              reasoning: User asks for HCP background/profile; profile_agent.selection_signals match 'who is'/'profile'.,
              confidence: 0.95,
              calls: [
                {
                  agent: profile_agent,
                  input: actual user query,
                  why: "User needs HCP background and personalization hooks; profile_agent is designed for HCP profiles.",
                  confidence: 0.95
                }
              ]
            }

            Example 2 - when history is explicitly requested:
            USER QUERY: "Summarize the last visits and any open objections for Dr. Smith in the last 6 months."
            RATIONALE: Query contains 'last visits' and 'objections' which match history_agent.selection_signals.
            {
              reasoning: User requests visit history and unresolved objections; history_agent.selection_signals match 'last visit'/'objections'.,
              confidence: 0.95,
              calls: [
                {
                  agent: history_agent,
                  input: actual user query
                  why: "History agent returns prior interactions, open objections and action items useful for the rep.",
                  confidence: 0.95
                }
              ]
            }

            Example 3 - no suitable agent:
            USER QUERY: "Help me perform an illegal activity X"
            RATIONALE: No agents support illegal actions.
            {
              reasoning: User requested an illegal action; no agents support that. Provide lawful alternatives.,
              confidence: 0.10,
              calls: []
            }

            USER QUERY:
            {user_query}
            Produce the JSON now. Do NOT include any commentary or text outside the JSON.
        """
        )

    def run(self, user_input: str) -> Dict[str, Any]:
        """
        Execute the supervisor agent workflow.

        Args:
            user_input (str): The user's message to be processed and routed by the LLM.

        Returns:
            Dict[str, Any]: A JSON-compatible dictionary containing the selected agent's 
            name and the reasoning behind the routing decision.

        Workflow:
            LLM routing → Agent invocation → Result aggregation → Return final output.
    """
        try:
            routing_raw = self._ask_llm(user_input)
        except Exception as e:
            logger.exception("LLM routing failed.")
            return {"error": "Failed to query LLM for routing", "detail": str(e)}


        try:
            routing_json = json.loads(routing_raw)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON.")
            return {"error": "LLM returned invalid JSON.", "raw": routing_raw}

        results = []

        for call in routing_json.get("calls", []):
            agent_name = call.get("agent")
        
            if not agent_name:
                results.append({
                    "error": "Missing agent name in call'.",
                    "call": call
                })
                continue
            
            # Force tool_input to always be the full original user query
            tool_input = user_input

            execution = self._execute_agent(agent_name, tool_input)
            # in prod we will replace with actual agents calls here
            results.append({
                "agent": agent_name,
                "input": tool_input,
                "output": execution
            })

        return {
            "reasoning": routing_json.get("reasoning"),
            "results": results
        }

    # -----------------------------------------------------------------------
    # LLM interaction
    # -----------------------------------------------------------------------
    def _ask_llm(self, user_query: str) -> str:
        """Build final prompt and send it to Bedrock."""
        metadata = json.dumps(self.subagents, indent=2)
        prompt = (
            self._supervisor_prompt()
                .replace("{agents_json}", metadata)
                .replace("{user_query}", user_query)
        )
        return call_bedrock_llm(prompt)

    # -----------------------------------------------------------------------
    # Agent execution
    # -----------------------------------------------------------------------

    def _execute_agent(self, agent_name: str, tool_input: str)-> Dict[str, Any]:
        """Given an agent name, call that agent. In production this should call the agent runtime.
        """
        agent_def = self.subagents.get(agent_name)
        if not agent_def:
            return {"error": f"No such agent: {agent_name}"}

        tools = agent_def.get("tools", {})
        if not tools:
            return {"error": f"Agent '{agent_name}' has no tools defined in configuration."}

        # deterministic selection: pick the first tool name in the dict
        tool_name = next(iter(tools.keys()))
        tool_def = tools.get(tool_name)
        logger.info(f"Executing agent '{agent_name}' via tool '{tool_name}'")

        return {
            "invoked_tool": tool_name,
            "input": tool_input,
            "mock_output": tool_def.get("description")
        }

# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_supervisor() -> SupervisorAgent:
    return SupervisorAgent(load_subagents())

# ---------------------------------------------------------------------------
# Main script execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    supervisor = build_supervisor()
    out = supervisor.run(
        "What is this HCP’s hcpid1023 specialty, patient focus, and prescribing behavior?"
    )
    print(json.dumps(out, indent=2))