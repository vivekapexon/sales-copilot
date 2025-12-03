# Design Document: Streamlit SALES-COPILOT UI

## Overview

This design document outlines the architecture and implementation approach for a Streamlit-based web interface for the Strategy Agent system. The application will provide a ChatGPT-like conversational interface with AWS theming, persistent chat history, and seamless integration with the existing strategy agent that orchestrates 6 specialized agents (Profile, History, Prescribing, Access, Competitive, and Content agents).

The design prioritizes simplicity, user experience, and maintainability while leveraging Streamlit's built-in capabilities for rapid UI development.

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Web UI                      │
│  ┌────────────┐  ┌──────────────────────────────────┐  │
│  │  Sidebar   │  │     Main Conversation Area       │  │
│  │            │  │                                  │  │
│  │  - New     │  │  ┌────────────────────────────┐ │  │
│  │    Chat    │  │  │   Message Display Area     │ │  │
│  │  - Chat    │  │  │   (Scrollable)             │ │  │
│  │    History │  │  │                            │ │  │
│  │  - Session │  │  │   User: [message]          │ │  │
│  │    List    │  │  │   Agent: [response]        │ │  │
│  │            │  │  └────────────────────────────┘ │  │
│  │            │  │                                  │  │
│  │            │  │  ┌────────────────────────────┐ │  │
│  │            │  │  │   Fixed Input Box          │ │  │
│  │            │  │  │   [Type message...] [Send] │ │  │
│  │            │  │  └────────────────────────────┘ │  │
│  └────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Session State Manager                       │
│  - Current session ID                                    │
│  - Active conversation messages                          │
│  - Chat history metadata                                 │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│           Chat History Storage (JSON Files)              │
│  - sessions.json (session metadata)                      │
│  - session_<id>.json (individual conversations)          │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│              Strategy Agent Integration                  │
│  - run_strategy_agent(nlq: str)                         │
│  - Returns agent response                                │
└─────────────────────────────────────────────────────────┘
```

### Component Architecture

1. **UI Layer (Streamlit Components)**
   - Header component with AWS branding
   - Sidebar component for chat history
   - Main conversation area with message display
   - Fixed input component at bottom

2. **State Management Layer**
   - Streamlit session state for active conversation
   - Session metadata management
   - Current session tracking

3. **Storage Layer**
   - JSON-based file storage for chat history
   - Session metadata storage
   - File-based persistence

4. **Agent Integration Layer**
   - Interface to existing strategy_agent.py
   - Response parsing and formatting
   - Error handling

## Components and Interfaces

### 1. Main Application Component (`app.py`)

**Responsibilities:**
- Initialize Streamlit page configuration
- Coordinate all UI components
- Manage application state
- Handle routing between components

**Key Functions:**
```python
def main():
    """Main application entry point"""
    
def initialize_session_state():
    """Initialize Streamlit session state variables"""
    
def apply_custom_css():
    """Apply AWS-themed custom CSS"""
```

### 2. Header Component

**Responsibilities:**
- Display AWS-themed header with SALES-COPILOT branding
- Maintain fixed position at top

**Implementation:**
- Use `st.markdown()` with custom HTML/CSS
- AWS color scheme: Orange (#FF9900), Dark Gray (#232F3E), White (#FFFFFF)

**CSS Styling:**
```css
.header {
    background-color: #232F3E;
    color: white;
    padding: 1rem;
    position: fixed;
    top: 0;
    width: 100%;
    z-index: 999;
    border-bottom: 3px solid #FF9900;
}
```

### 3. Sidebar Component

**Responsibilities:**
- Display "New Chat" button
- List all previous chat sessions
- Handle session selection
- Provide delete functionality for sessions

**Key Functions:**
```python
def render_sidebar():
    """Render sidebar with chat history"""
    
def create_new_chat():
    """Create a new chat session"""
    
def load_chat_session(session_id: str):
    """Load a specific chat session"""
    
def delete_chat_session(session_id: str):
    """Delete a chat session"""
```

**Data Structure:**
```python
{
    "session_id": "uuid-string",
    "created_at": "2025-12-03T10:30:00",
    "last_updated": "2025-12-03T10:45:00",
    "preview": "First message preview...",
    "message_count": 5
}
```

### 4. Conversation Display Component

**Responsibilities:**
- Render all messages in the current conversation
- Differentiate between user and agent messages
- Format JSON responses appropriately
- Auto-scroll to latest message

**Key Functions:**
```python
def render_conversation():
    """Render all messages in current conversation"""
    
def render_user_message(message: str, timestamp: str):
    """Render a user message"""
    
def render_agent_message(message: dict, timestamp: str):
    """Render an agent response with formatting"""
    
def format_json_response(response: dict) -> str:
    """Format JSON response for display"""
```

**Message Data Structure:**
```python
{
    "role": "user" | "agent",
    "content": str | dict,
    "timestamp": "2025-12-03T10:30:00",
    "message_id": "uuid-string"
}
```

### 5. Input Component

**Responsibilities:**
- Provide fixed input box at bottom
- Handle message submission
- Show loading state during processing
- Disable during agent processing

**Key Functions:**
```python
def render_input_box():
    """Render fixed input box at bottom"""
    
def handle_message_submission(user_input: str):
    """Process user message and get agent response"""
    
def show_loading_indicator():
    """Display loading animation while agent processes"""
```

### 6. Chat Storage Manager

**Responsibilities:**
- Save and load chat sessions
- Manage session metadata
- Handle file I/O operations
- Ensure data persistence

**Key Functions:**
```python
class ChatStorageManager:
    def __init__(self, storage_dir: str = "chat_history"):
        """Initialize storage manager"""
        
    def save_message(self, session_id: str, message: dict):
        """Save a message to session"""
        
    def load_session(self, session_id: str) -> list:
        """Load all messages from a session"""
        
    def get_all_sessions(self) -> list:
        """Get metadata for all sessions"""
        
    def delete_session(self, session_id: str):
        """Delete a session and its data"""
        
    def create_session(self) -> str:
        """Create a new session and return ID"""
```

**Storage Structure:**
```
chat_history/
├── sessions.json          # Metadata for all sessions
├── session_<uuid1>.json   # Messages for session 1
├── session_<uuid2>.json   # Messages for session 2
└── ...
```

### 7. Agent Integration Module

**Responsibilities:**
- Interface with existing strategy_agent.py
- Parse agent responses
- Handle errors from agent
- Format responses for UI display

**Key Functions:**
```python
def call_strategy_agent(user_input: str) -> dict:
    """Call strategy agent and return formatted response"""
    
def parse_agent_response(raw_response) -> dict:
    """Parse and structure agent response"""
    
def handle_agent_error(error) -> dict:
    """Handle and format agent errors"""
```

### 8. Response Formatter

**Responsibilities:**
- Format different types of agent responses
- Handle JSON formatting
- Create expandable sections for complex data
- Syntax highlighting for JSON

**Key Functions:**
```python
def format_profile_agent_response(data: dict) -> str:
    """Format Profile Agent response"""
    
def format_prescribing_agent_response(data: dict) -> str:
    """Format Prescribing Agent response"""
    
def format_multi_agent_response(data: list) -> str:
    """Format response from multiple agents"""
    
def create_json_expander(data: dict, title: str) -> None:
    """Create expandable JSON section"""
```

## Data Models

### Session Model
```python
@dataclass
class ChatSession:
    session_id: str
    created_at: datetime
    last_updated: datetime
    preview: str
    message_count: int
```

### Message Model
```python
@dataclass
class Message:
    message_id: str
    role: Literal["user", "agent"]
    content: Union[str, dict]
    timestamp: datetime
    session_id: str
```

### Agent Response Model
```python
@dataclass
class AgentResponse:
    success: bool
    data: Union[dict, list, str]
    error: Optional[str]
    agent_names: List[str]  # Which agents were called
```

## Error Handling

### Error Categories

1. **Agent Execution Errors**
   - Strategy agent fails to respond
   - Individual agent failures
   - Missing parameters

2. **Storage Errors**
   - File I/O failures
   - Corrupted session data
   - Disk space issues

3. **UI Errors**
   - Invalid user input
   - Session state corruption
   - Rendering failures

### Error Handling Strategy

```python
def handle_error(error_type: str, error: Exception) -> dict:
    """
    Centralized error handling
    
    Returns:
        dict with error message and suggested action
    """
    error_messages = {
        "agent_error": "The agent encountered an issue. Please try again.",
        "storage_error": "Failed to save chat history. Your message was processed but not saved.",
        "missing_params": "Please provide required information: {params}",
        "network_error": "Connection issue. Please check your network and retry."
    }
    
    # Log error for debugging
    log_error(error_type, error)
    
    # Return user-friendly message
    return {
        "error": True,
        "message": error_messages.get(error_type, "An unexpected error occurred."),
        "details": str(error) if DEBUG_MODE else None
    }
```

### Error Display

- Use `st.error()` for critical errors
- Use `st.warning()` for non-critical issues
- Use `st.info()` for informational messages
- Provide retry buttons where appropriate

## Testing Strategy

### Unit Tests

1. **Storage Manager Tests**
   - Test session creation
   - Test message saving/loading
   - Test session deletion
   - Test error handling for corrupted data

2. **Response Formatter Tests**
   - Test JSON formatting
   - Test different agent response types
   - Test edge cases (empty responses, malformed JSON)

3. **Agent Integration Tests**
   - Mock strategy agent responses
   - Test error handling
   - Test response parsing

### Integration Tests

1. **End-to-End Flow Tests**
   - Test complete user interaction flow
   - Test session persistence across app restarts
   - Test multi-turn conversations

2. **UI Component Tests**
   - Test sidebar functionality
   - Test message display
   - Test input handling

### Manual Testing Checklist

- [ ] AWS theme displays correctly
- [ ] Chat history persists after closing app
- [ ] Follow-up questions maintain context
- [ ] JSON responses are formatted properly
- [ ] Error messages display appropriately
- [ ] Input box remains fixed at bottom
- [ ] Sidebar session list updates correctly
- [ ] Delete session functionality works
- [ ] Loading indicators appear during processing
- [ ] Responsive design works on different screen sizes

## Styling and Theming

### AWS Color Palette

```python
AWS_COLORS = {
    "primary_orange": "#FF9900",
    "dark_gray": "#232F3E",
    "light_gray": "#EAEDED",
    "white": "#FFFFFF",
    "text_dark": "#16191F",
    "border_gray": "#AAB7B8",
    "success_green": "#1D8102",
    "error_red": "#D13212"
}
```

### Custom CSS

```css
/* Header */
.sales-copilot-header {
    background: linear-gradient(90deg, #232F3E 0%, #37475A 100%);
    color: white;
    padding: 1rem 2rem;
    border-bottom: 3px solid #FF9900;
    font-size: 1.5rem;
    font-weight: bold;
}

/* User Message */
.user-message {
    background-color: #FF9900;
    color: white;
    padding: 1rem;
    border-radius: 10px;
    margin: 0.5rem 0;
    margin-left: 20%;
    text-align: right;
}

/* Agent Message */
.agent-message {
    background-color: #EAEDED;
    color: #16191F;
    padding: 1rem;
    border-radius: 10px;
    margin: 0.5rem 0;
    margin-right: 20%;
    border-left: 4px solid #FF9900;
}

/* Input Box */
.fixed-input {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background-color: white;
    padding: 1rem;
    border-top: 2px solid #AAB7B8;
    box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
}

/* Sidebar */
.sidebar-session {
    padding: 0.75rem;
    margin: 0.5rem 0;
    border-radius: 5px;
    border-left: 3px solid #FF9900;
    background-color: #EAEDED;
    cursor: pointer;
    transition: background-color 0.2s;
}

.sidebar-session:hover {
    background-color: #D5DBDB;
}
```

## Performance Considerations

1. **Lazy Loading**
   - Load only recent sessions in sidebar initially
   - Implement pagination for large chat histories

2. **Message Rendering**
   - Use Streamlit's caching for static content
   - Optimize JSON formatting for large responses

3. **Storage Optimization**
   - Compress old session files
   - Implement session archiving for very old chats
   - Limit maximum messages per session

4. **Agent Response Handling**
   - Implement timeout for agent calls (30 seconds)
   - Show progress indicators for long-running operations
   - Cache frequently requested information

## Security Considerations

1. **Input Validation**
   - Sanitize user input before passing to agent
   - Validate session IDs to prevent path traversal

2. **Data Storage**
   - Store chat history in user-specific directory
   - Implement file permissions appropriately
   - Consider encryption for sensitive data

3. **Error Messages**
   - Don't expose internal system details in errors
   - Log detailed errors separately for debugging

## Deployment Considerations

1. **Environment Setup**
   - Python 3.8+
   - Streamlit 1.28+
   - Dependencies from existing strategy_agent.py

2. **Configuration**
   - Environment variables for storage paths
   - Configurable agent timeout
   - Debug mode toggle

3. **Running the Application**
   ```bash
   streamlit run app.py --server.port 8501
   ```

## Future Enhancements

1. **Export Functionality**
   - Export conversations to PDF
   - Export to CSV for analysis

2. **Search Functionality**
   - Search across all chat sessions
   - Filter by date range or agent type

3. **User Preferences**
   - Theme customization
   - Font size adjustment
   - Message density options

4. **Analytics Dashboard**
   - Most used agents
   - Average response time
   - Common query patterns

5. **Multi-User Support**
   - User authentication
   - User-specific chat histories
   - Shared sessions for team collaboration
