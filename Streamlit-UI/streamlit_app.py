"""
SALES-COPILOT Streamlit Application
Main entry point for the AWS-themed conversational interface
"""

import streamlit as st
from datetime import datetime
import sys
import os
import json
import html

# Add Strategy-Agent to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Strategy-Agent'))

# Import utilities (will be created in subsequent tasks)
from utils.storage_manager import ChatStorageManager
from utils.agent_integration import call_strategy_agent, AGENT_AVAILABLE, USING_MOCK
from utils.response_formatter import format_agent_response
from utils.styles import get_custom_css, AWS_COLORS
from utils.error_handler import handle_error

def main():
    """Main application entry point"""
    # Page configuration
    st.set_page_config(
        page_title="SALES-COPILOT",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Apply custom CSS
    st.markdown(get_custom_css(), unsafe_allow_html=True)
    
    # Initialize session state
    initialize_session_state()
    
    # Show warning if using mock agent
    if USING_MOCK:
        st.warning(
            "⚠️ **Using Mock Agent** - You're seeing sample data. "
            "To use the real Strategy Agent, please resolve the dependency issue. "
            "See TROUBLESHOOTING.md for solutions.",
            icon="⚠️"
        )
    elif not AGENT_AVAILABLE:
        st.error(
            "❌ **Agent Not Available** - Neither real nor mock agent could be loaded. "
            "Please check your installation. See TROUBLESHOOTING.md for help.",
            icon="❌"
        )
    
    # Render components
    render_header()
    render_sidebar()
    render_conversation()
    render_input_box()


def _json_to_html(value, level: int = 0) -> str:
    """
    Recursively convert a Python object (dict / list / primitive)
    into nested HTML lists suitable for display in the chat bubble.
    """
    indent = "  " * level
 
    # Dict → <ul><li>key: value</li>...</ul>
    if isinstance(value, dict):
        items = []
        for key, val in value.items():
            key_html = f"<span class='json-key'>{html.escape(str(key))}</span>"
            val_html = _json_to_html(val, level + 1)
            items.append(f"{indent}<li>{key_html}: {val_html}</li>")
        return "<ul class='json-object'>\n" + "\n".join(items) + f"\n{indent}</ul>"
 
    # List → <ul><li>item</li>...</ul>
    elif isinstance(value, list):
        items = []
        for item in value:
            items.append(f"{indent}<li>{_json_to_html(item, level + 1)}</li>")
        return "<ul class='json-array'>\n" + "\n".join(items) + f"\n{indent}</ul>"
 
    # Primitives
    else:
        if isinstance(value, str):
            # Wrap strings in quotes
            return f"<span class='json-string'>\"{html.escape(value)}\"</span>"
        elif isinstance(value, bool):
            return f"<span class='json-bool'>{str(value).lower()}</span>"
        elif value is None:
            return "<span class='json-null'>null</span>"
        else:  # int, float, etc.
            return f"<span class='json-number'>{value}</span>"

def initialize_session_state():
    """Initialize Streamlit session state variables"""
    # Initialize storage manager
    if 'storage_manager' not in st.session_state:
        st.session_state.storage_manager = ChatStorageManager()
    
    # Initialize current session ID
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = st.session_state.storage_manager.create_session()
    
    # Load messages for current session
    if 'messages' not in st.session_state:
        st.session_state.messages = st.session_state.storage_manager.load_session(
            st.session_state.current_session_id
        )
    
    # Load all chat sessions
    if 'chat_sessions' not in st.session_state:
        st.session_state.chat_sessions = st.session_state.storage_manager.get_all_sessions()
    
    # Processing flag
    if 'is_processing' not in st.session_state:
        st.session_state.is_processing = False


def render_header():
    """Render AWS-themed header with SALES-COPILOT branding"""
    st.markdown(
        f"""
        <div class="sales-copilot-header">
            <span style="color: {AWS_COLORS['primary_orange']}">SALES</span>-COPILOT
        </div>
        """,
        unsafe_allow_html=True
    )


def render_sidebar():
    """Render sidebar with chat history"""
    with st.sidebar:
        st.title("💬 Chat History")
        
        # New Chat button
        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            create_new_chat()
        
        st.divider()
        
        # Refresh sessions list
        st.session_state.chat_sessions = st.session_state.storage_manager.get_all_sessions()
        
        # Display chat sessions
        if not st.session_state.chat_sessions:
            st.markdown(
                '<div class="empty-state">'
                '<div class="empty-state-icon">📭</div>'
                '<p>No chat history yet.<br>Start a new conversation!</p>'
                '</div>',
                unsafe_allow_html=True
            )
        else:
            for session in st.session_state.chat_sessions:
                render_session_item(session)


def render_conversation():
    """Render all messages in current conversation"""
    from datetime import datetime
    
    # Container for messages
    st.markdown('<div class="conversation-container">', unsafe_allow_html=True)
    
    if not st.session_state.messages:
        # Empty state
        st.markdown(
            """
            <div class="empty-state">
                <div class="empty-state-icon">🤖</div>
                <h3>Welcome to SALES-COPILOT</h3>
                <p>Ask me about HCP profiles, prescribing trends, access intelligence,<br>
                competitive insights, or get a complete pre-call brief!</p>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        # Render all messages
        for message in st.session_state.messages:
            if message['role'] == 'user':
                render_user_message(message['content'], message.get('timestamp', ''))
            else:
                render_agent_message(message['content'], message.get('timestamp', ''))
    
    st.markdown('</div>', unsafe_allow_html=True)


def render_user_message(content: str, timestamp: str):
    """Render a user message"""
    from datetime import datetime
    
    # Format timestamp
    time_str = ""
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%I:%M %p")
        except:
            pass
    
    st.markdown(
        f"""
        <div class="user-message">
            {content}
            {f'<div class="message-timestamp">{time_str}</div>' if time_str else ''}
        </div>
        """,
        unsafe_allow_html=True
    )


# def render_agent_message(content: dict, timestamp: str):
#     """Render an agent response"""
#     from datetime import datetime
    
#     # Format timestamp
#     time_str = ""
#     if timestamp:
#         try:
#             dt = datetime.fromisoformat(timestamp)
#             time_str = dt.strftime("%I:%M %p")
#         except:
#             pass
    
#     # Format the content
#     formatted_content = format_agent_response(content)
    
#     st.markdown(
#         f"""
#         <div class="agent-message">
#             {formatted_content}
#             {f'<div class="message-timestamp">{time_str}</div>' if time_str else ''}
#         </div>
#         """,
#         unsafe_allow_html=True
#     )

def render_agent_message(content: dict, timestamp: str):
    """Render an agent response (supports nested JSON from backend)"""
    from datetime import datetime
 
    # Try to parse JSON if backend returned a string
    content_obj = content
    if isinstance(content, str):
        try:
            content_obj = json.loads(content)
        except json.JSONDecodeError:
            # Not valid JSON, keep the raw string
            content_obj = content
 
    # Format timestamp
    time_str = ""
    if timestamp:
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%I:%M %p")
        except Exception:
            pass
 
    # Decide how to render
    if isinstance(content_obj, dict) and content_obj.get("type") == "error":
        # Keep your existing error formatting logic
        formatted_content = format_agent_response(content_obj)
    elif isinstance(content_obj, (dict, list)):
        # Generic nested JSON → HTML tree
        formatted_content = _json_to_html(content_obj)
    else:
        # Fallback: use existing formatter (e.g., plain text, markdown, etc.)
        formatted_content = format_agent_response(content_obj)
 
    st.markdown(
        f"""
<div class="agent-message">
            {formatted_content}
            {f'<div class="message-timestamp">{time_str}</div>' if time_str else ''}
</div>
        """,
        unsafe_allow_html=True
    )


def render_input_box():
    """Render fixed input box at bottom"""
    user_input = st.chat_input(
        "Ask about HCP profiles, prescribing trends, or get pre-call briefs...",
        disabled=st.session_state.is_processing
    )
    
    if user_input and not st.session_state.is_processing:
        handle_message_submission(user_input)


def handle_message_submission(user_input: str):
    """Process user message and get agent response"""
    from datetime import datetime
    from utils.error_handler import handle_error, display_error
    
    # Set processing flag
    st.session_state.is_processing = True
    
    try:
        # Create user message
        user_message = {
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat(),
            "message_id": str(datetime.now().timestamp())
        }
        
        # Add to messages and save
        st.session_state.messages.append(user_message)
        st.session_state.storage_manager.save_message(
            st.session_state.current_session_id,
            user_message
        )
        
        # Show loading indicator
        with st.spinner("🤖 Agent is thinking..."):
            # Call strategy agent
            response = call_strategy_agent(user_input, st.session_state.messages)
        
        # Check if response was successful
        if response.get('success', False):
            # Create agent message
            agent_message = {
                "role": "agent",
                "content": response.get('data', {}),
                "timestamp": datetime.now().isoformat(),
                "message_id": str(datetime.now().timestamp()),
                "agent_names": response.get('agent_names', [])
            }
            
            # Add to messages and save
            st.session_state.messages.append(agent_message)
            st.session_state.storage_manager.save_message(
                st.session_state.current_session_id,
                agent_message
            )
        else:
            # Handle error response
            error_message = response.get('error', 'Unknown error occurred')
            error_type = response.get('error_type', 'agent_error')
            
            # Create error message for display
            agent_message = {
                "role": "agent",
                "content": {
                    "type": "error",
                    "message": error_message,
                    "error_type": error_type
                },
                "timestamp": datetime.now().isoformat(),
                "message_id": str(datetime.now().timestamp())
            }
            
            st.session_state.messages.append(agent_message)
            st.session_state.storage_manager.save_message(
                st.session_state.current_session_id,
                agent_message
            )
        
    except Exception as e:
        # Handle unexpected errors
        error_dict = handle_error("agent_error", e)
        display_error(error_dict)
    
    finally:
        # Reset processing flag
        st.session_state.is_processing = False
        # Rerun to update UI
        st.rerun()


def render_session_item(session: dict):
    """Render a single session item in sidebar"""
    from datetime import datetime
    
    session_id = session['session_id']
    preview = session.get('preview', 'New conversation')
    last_updated = session.get('last_updated', '')
    message_count = session.get('message_count', 0)
    
    # Format timestamp
    try:
        dt = datetime.fromisoformat(last_updated)
        time_str = dt.strftime("%b %d, %I:%M %p")
    except:
        time_str = ""
    
    # Check if this is the active session
    is_active = session_id == st.session_state.current_session_id
    
    # Create container for session
    col1, col2 = st.columns([4, 1])
    
    with col1:
        # Session button
        if st.button(
            f"💬 {preview[:30]}{'...' if len(preview) > 30 else ''}",
            key=f"session_{session_id}",
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            load_chat_session(session_id)
    
    with col2:
        # Delete button
        if st.button("🗑️", key=f"delete_{session_id}", help="Delete this chat"):
            delete_chat_session(session_id)
    
    # Show metadata
    if time_str or message_count:
        st.caption(f"🕒 {time_str} • {message_count} messages")
    
    st.divider()


def create_new_chat():
    """Create a new chat session"""
    st.session_state.current_session_id = st.session_state.storage_manager.create_session()
    st.session_state.messages = []
    st.rerun()


def load_chat_session(session_id: str):
    """Load a specific chat session"""
    st.session_state.current_session_id = session_id
    st.session_state.messages = st.session_state.storage_manager.load_session(session_id)
    st.rerun()


def delete_chat_session(session_id: str):
    """Delete a chat session"""
    # Delete from storage
    st.session_state.storage_manager.delete_session(session_id)
    
    # If we deleted the active session, create a new one
    if session_id == st.session_state.current_session_id:
        create_new_chat()
    else:
        st.rerun()


if __name__ == "__main__":
    main()
