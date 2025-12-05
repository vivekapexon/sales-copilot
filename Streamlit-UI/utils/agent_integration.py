"""
Agent Integration Module
Interfaces with the Strategy Agent and handles responses
"""

import sys
import os
from typing import Dict, Any, Optional
import signal
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # .../Streamlit-UI
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# -------------------------------------------------------
# Imports & availability flags
# -------------------------------------------------------
try:
    from Strategy_Agent.strategy_agent import run_strategy_agent  # type: ignore
    from post_call.supervisor_agent import run_supervisor_agent   # type: ignore

    
    AGENT_AVAILABLE = True
    USING_MOCK = False
    print("✓ Sales Copilot Agents loaded successfully (pre-call & post-call)")
except ImportError as e:
    print(f"⚠ Warning: Could not import strategy_agent/post_call supervisor_agent: {e}")
    print("\nAttempting to use mock agent for testing (pre-call only)...")
    try:
        from mock_strategy_agent import run_strategy_agent#type:ignore
        run_supervisor_agent = None
        AGENT_AVAILABLE = True
        USING_MOCK = True
        print("✓ Mock pre-call agent loaded - UI will work but with sample data")
        print("\nTo use the real agents, please install required dependencies:")
        print("  pip install strands")
        print("\nIf you're on Windows and getting DLL errors:")
        print("  1. Install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe")
        print("  2. pip install --upgrade pip setuptools wheel")
        print("  3. pip install strands --no-cache-dir")
        print("\nSee TROUBLESHOOTING.md for more solutions")
    except ImportError:
        run_strategy_agent = None
        run_supervisor_agent = None
        AGENT_AVAILABLE = False
        USING_MOCK = False
        print("✗ Neither real nor mock agents available")


class TimeoutException(Exception):
    """Exception raised when agent call times out"""
    pass


@contextmanager
def timeout(seconds: int):
    """Context manager for timeout handling"""
    def timeout_handler(signum, frame):
        raise TimeoutException("Agent call timed out")
    
    # Set the signal handler
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)#type:ignore
    signal.alarm(seconds)#type:ignore
    
    try:
        yield
    finally:
        signal.alarm(0)#type:ignore
        signal.signal(signal.SIGALRM, old_handler)#type:ignore


# --------------------------------------------------------------------
# Shared helper: build enhanced input with conversation context
# --------------------------------------------------------------------
def _build_enhanced_input(user_input: str, conversation_history: Optional[list]) -> str:
    """
    Build a context-aware input string from the last few messages.
    Used by both pre-call and post-call agents.
    """
    enhanced_input = user_input

    if conversation_history and len(conversation_history) > 1:
        # Get last few messages for context (last 3 exchanges = ~6 messages)
        recent_messages = conversation_history[-6:]

        context_parts = []
        for msg in recent_messages[:-1]:  # Exclude current user message
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')

            if role == 'user':
                context_parts.append(f"Previous question: {content}")
            elif role == 'agent' and isinstance(content, dict):
                agent_names = msg.get('agent_names', [])
                if agent_names:
                    context_parts.append(
                        f"Previous response from: {', '.join(agent_names)}"
                    )

        if context_parts:
            context_str = "\n".join(context_parts[-4:])  # Last 2 exchanges
            enhanced_input = (
                "Context from previous conversation:\n"
                f"{context_str}\n\n"
                f"Current question: {user_input}"
            )

    return enhanced_input

# --------------------------------------------------------------------
# PRE-CALL STRATEGY AGENT
# --------------------------------------------------------------------
def call_strategy_agent(user_input: str, conversation_history: Optional[list] = None) -> Dict[str, Any]:
    """
    Call pre-call strategy agent and return formatted response
    
    Args:
        user_input: User's natural language query
        conversation_history: Optional list of previous messages for context
        
    Returns:
        Dict with success status, data, error message, and agent names
    """
    if run_strategy_agent is None:
        return handle_agent_error(
            Exception("Strategy agent not available. Please check installation.")
        )
    
    try:
        enhanced_input = _build_enhanced_input(user_input, conversation_history)

        # Call agent with timeout (disabled on Windows by signal.SIGALRM issues)
        try:
            # Note: Windows doesn't support signal.SIGALRM, so we'll skip timeout for now
            # and implement it differently if needed
            raw_response = run_strategy_agent(enhanced_input)
        except Exception as e:
            return handle_agent_error(e)
        
        # Parse the response
        parsed_response = parse_agent_response(raw_response)
        
        return {
            "success": True,
            "data": parsed_response,
            "error": None,
            "agent_names": extract_agent_names(parsed_response),
        }
        
    except TimeoutException:
        return {
            "success": False,
            "data": None,
            "error": "The agent took too long to respond. Please try again.",
            "agent_names": [],
        }
    except Exception as e:
        return handle_agent_error(e)


# --------------------------------------------------------------------
# POST-CALL SUPERVISOR AGENT
# --------------------------------------------------------------------
def call_postcall_agent(
    user_input: str,
    conversation_history: Optional[list] = None
) -> Dict[str, Any]:
    """
    Call post-call supervisor agent and return formatted response.
    
    Args:
        user_input: User's natural language query
        conversation_history: Optional list of previous messages for context
        
    Returns:
        Dict with success status, data, error message, and agent names
    """
    if run_supervisor_agent is None:
        return handle_agent_error(
            Exception("Post-call supervisor agent not available. Please check installation.")
        )
    
    try:
        enhanced_input = _build_enhanced_input(user_input, conversation_history)

        try:
            # Adjust this call if your supervisor_agent signature differs
            # e.g. supervisor_agent(enhanced_input, conversation_history=conversation_history)
            raw_response = run_supervisor_agent(enhanced_input)
        except Exception as e:
            return handle_agent_error(e)
        
        parsed_response = parse_agent_response(raw_response)
        
        return {
            "success": True,
            "data": parsed_response,
            "error": None,
            "agent_names": extract_agent_names(parsed_response),
        }
    
    except TimeoutException:
        return {
            "success": False,
            "data": None,
            "error": "The post-call agent took too long to respond. Please try again.",
            "agent_names": [],
        }
    except Exception as e:
        return handle_agent_error(e)


# --------------------------------------------------------------------
# Shared helpers: parsing, errors, agent name extraction
# --------------------------------------------------------------------
def parse_agent_response(raw_response: Any) -> Dict[str, Any]:
    """
    Parse and structure agent response
    
    Args:
        raw_response: Raw response from strategy or post-call agent
        
    Returns:
        Structured response dictionary
    """
    # If response is already a dict, return it
    if isinstance(raw_response, dict):
        return raw_response
    
    # If response is a string, try to parse as JSON
    if isinstance(raw_response, str):
        import json
        try:
            return json.loads(raw_response)
        except json.JSONDecodeError:
            # Return as plain text response
            return {
                "type": "text",
                "content": raw_response
            }
    
    # If response is a list, assume it's multiple agent responses
    if isinstance(raw_response, list):
        return {
            "type": "multi_agent",
            "agents": raw_response
        }
    
    # Default: convert to string
    return {
        "type": "text",
        "content": str(raw_response)
    }


def handle_agent_error(error: Exception) -> Dict[str, Any]:
    """
    Handle and format agent errors
    
    Args:
        error: Exception that occurred
        
    Returns:
        Error response dictionary
    """
    error_message = str(error)
    
    # Check for specific error types
    if "missing_parameters" in error_message.lower():
        return {
            "success": False,
            "data": None,
            "error": f"Missing required information: {error_message}",
            "agent_names": [],
            "error_type": "missing_parameters"
        }
    elif "connection" in error_message.lower() or "network" in error_message.lower():
        return {
            "success": False,
            "data": None,
            "error": "Connection issue. Please check your network and try again.",
            "agent_names": [],
            "error_type": "network_error"
        }
    else:
        return {
            "success": False,
            "data": None,
            "error": f"The agent encountered an issue: {error_message}",
            "agent_names": [],
            "error_type": "agent_error"
        }


def extract_agent_names(response: Dict[str, Any]) -> list:
    """
    Extract agent names from response
    
    Args:
        response: Parsed agent response
        
    Returns:
        List of agent names that were called
    """
    agent_names = []
    
    # Check if response has Agent field
    if isinstance(response, dict):
        if "Agent" in response:
            agent_names.append(response["Agent"])
        elif "agents" in response and isinstance(response["agents"], list):
            for agent_data in response["agents"]:
                if isinstance(agent_data, dict) and "Agent" in agent_data:
                    agent_names.append(agent_data["Agent"])
    
    return agent_names
