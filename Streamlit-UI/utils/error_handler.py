"""
Error Handler Module
Centralized error handling and user feedback
"""

import streamlit as st
from typing import Dict, Any, Optional
import traceback
from datetime import datetime


# Error message templates
ERROR_MESSAGES = {
    "agent_error": "The agent encountered an issue processing your request. Please try again.",
    "storage_error": "Failed to save chat history. Your message was processed but not saved.",
    "missing_params": "Please provide the required information: {params}",
    "network_error": "Connection issue detected. Please check your network and retry.",
    "timeout_error": "The request took too long to process. Please try again.",
    "unknown_error": "An unexpected error occurred. Please try again."
}


def handle_error(error_type: str, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Centralized error handling
    
    Args:
        error_type: Type of error (agent_error, storage_error, etc.)
        error: The exception that occurred
        context: Optional context information
        
    Returns:
        Dict with error message and suggested action
    """
    # Log error for debugging
    log_error(error_type, error, context)
    
    # Get user-friendly message
    message = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["unknown_error"])
    
    # Format message with context if needed
    if error_type == "missing_params" and context and "params" in context:
        message = message.format(params=", ".join(context["params"]))
    
    return {
        "error": True,
        "error_type": error_type,
        "message": message,
        "details": str(error),
        "timestamp": datetime.now().isoformat()
    }


def log_error(error_type: str, error: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Log error for debugging
    
    Args:
        error_type: Type of error
        error: The exception
        context: Optional context information
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    error_msg = f"[{timestamp}] {error_type}: {str(error)}"
    
    if context:
        error_msg += f"\nContext: {context}"
    
    # Print to console (in production, this would go to a proper logging system)
    print(error_msg)
    print(traceback.format_exc())


def display_error(error_dict: Dict[str, Any]):
    """
    Display error message in Streamlit UI
    
    Args:
        error_dict: Error dictionary from handle_error()
    """
    error_type = error_dict.get("error_type", "unknown_error")
    message = error_dict.get("message", "An error occurred")
    
    if error_type in ["agent_error", "timeout_error", "network_error"]:
        st.error(f"❌ {message}")
    elif error_type == "storage_error":
        st.warning(f"⚠️ {message}")
    elif error_type == "missing_params":
        st.info(f"ℹ️ {message}")
    else:
        st.error(f"❌ {message}")


def display_warning(message: str):
    """
    Display warning message
    
    Args:
        message: Warning message to display
    """
    st.warning(f"⚠️ {message}")


def display_info(message: str):
    """
    Display informational message
    
    Args:
        message: Info message to display
    """
    st.info(f"ℹ️ {message}")


def display_success(message: str):
    """
    Display success message
    
    Args:
        message: Success message to display
    """
    st.success(f"✅ {message}")


def create_retry_button(callback, label: str = "Retry") -> bool:
    """
    Create a retry button for error recovery
    
    Args:
        callback: Function to call when retry is clicked
        label: Button label
        
    Returns:
        True if button was clicked
    """
    if st.button(label, key=f"retry_{datetime.now().timestamp()}"):
        callback()
        return True
    return False
