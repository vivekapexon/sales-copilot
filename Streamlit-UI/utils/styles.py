"""
Styles Module
AWS-themed color palette and CSS definitions
"""

# AWS Color Palette
AWS_COLORS = {
    "primary_orange": "#FF9900",
    "dark_gray": "#232F3E",
    "light_gray": "#EAEDED",
    "white": "#FFFFFF",
    "text_dark": "#16191F",
    "border_gray": "#AAB7B8",
    "success_green": "#1D8102",
    "error_red": "#D13212",
    "medium_gray": "#37475A",
    "hover_gray": "#D5DBDB"
}


def get_custom_css() -> str:
    """
    Get custom CSS for AWS-themed styling
    
    Returns:
        CSS string to be injected into Streamlit app
    """
    return f"""
    <style>
        /* Global Styles */
        .stApp {{
            background-color: {AWS_COLORS['white']};
        }}
        
        /* Header Styles */
        .sales-copilot-header {{
            background: linear-gradient(90deg, {AWS_COLORS['dark_gray']} 0%, {AWS_COLORS['medium_gray']} 100%);
            color: {AWS_COLORS['white']};
            padding: 1.5rem 2rem;
            border-bottom: 4px solid {AWS_COLORS['primary_orange']};
            font-size: 1.8rem;
            font-weight: bold;
            margin: -1rem -1rem 2rem -1rem;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        /* Conversation Container */
        .conversation-container {{
            padding: 1rem;
            margin-bottom: 100px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }}
        
        /* User Message Styles */
        .user-message {{
            background-color: {AWS_COLORS['primary_orange']};
            color: {AWS_COLORS['white']};
            padding: 1rem 1.5rem;
            border-radius: 12px;
            margin: 1rem 0;
            margin-left: 20%;
            text-align: left;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            font-size: 1rem;
            line-height: 1.5;
        }}
        
        /* Agent Message Styles */
        .agent-message {{
            background-color: {AWS_COLORS['light_gray']};
            color: {AWS_COLORS['text_dark']};
            padding: 1.5rem;
            border-radius: 12px;
            margin: 1rem 0;
            margin-right: 20%;
            border-left: 5px solid {AWS_COLORS['primary_orange']};
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            font-size: 1rem;
            line-height: 1.6;
        }}
        
        .agent-message pre {{
            background-color: {AWS_COLORS['white']};
            padding: 1rem;
            border-radius: 6px;
            overflow-x: auto;
            border: 1px solid {AWS_COLORS['border_gray']};
            margin: 0.5rem 0;
        }}
        
        .agent-message strong {{
            color: {AWS_COLORS['dark_gray']};
        }}
        
        .agent-message details {{
            margin-top: 1rem;
            cursor: pointer;
        }}
        
        .agent-message summary {{
            color: {AWS_COLORS['primary_orange']};
            font-weight: bold;
            padding: 0.5rem;
            background-color: {AWS_COLORS['white']};
            border-radius: 4px;
            border: 1px solid {AWS_COLORS['border_gray']};
        }}
        
        .agent-message summary:hover {{
            background-color: {AWS_COLORS['light_gray']};
        }}
        
        .agent-message ul {{
            margin: 0.5rem 0;
            padding-left: 1.5rem;
        }}
        
        .agent-message li {{
            margin: 0.5rem 0;
        }}
        
        .agent-message hr {{
            border: none;
            border-top: 2px solid {AWS_COLORS['primary_orange']};
            margin: 1.5rem 0;
        }}
        
        /* Sidebar Styles */
        .css-1d391kg {{
            background-color: {AWS_COLORS['light_gray']};
        }}
        
        [data-testid="stSidebar"] {{
            background-color: {AWS_COLORS['light_gray']};
        }}
        
        .sidebar-session {{
            padding: 0.75rem;
            margin: 0.5rem 0;
            border-radius: 6px;
            border-left: 4px solid {AWS_COLORS['primary_orange']};
            background-color: {AWS_COLORS['white']};
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .sidebar-session:hover {{
            background-color: {AWS_COLORS['hover_gray']};
            transform: translateX(4px);
        }}
        
        .sidebar-session-active {{
            background-color: {AWS_COLORS['primary_orange']};
            color: {AWS_COLORS['white']};
            border-left: 4px solid {AWS_COLORS['dark_gray']};
        }}
        
        .sidebar-session-preview {{
            font-size: 0.85rem;
            color: {AWS_COLORS['text_dark']};
            margin-top: 0.25rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        
        .sidebar-session-time {{
            font-size: 0.75rem;
            color: {AWS_COLORS['border_gray']};
            margin-top: 0.25rem;
        }}
        
        /* Button Styles */
        .stButton > button {{
            background-color: {AWS_COLORS['primary_orange']};
            color: {AWS_COLORS['white']};
            border: none;
            border-radius: 6px;
            padding: 0.5rem 1.5rem;
            font-weight: bold;
            transition: all 0.2s ease;
        }}
        
        .stButton > button:hover {{
            background-color: {AWS_COLORS['dark_gray']};
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }}
        
        /* Chat Input Styles */
        .stChatInput {{
            border-top: 2px solid {AWS_COLORS['border_gray']};
            background-color: {AWS_COLORS['white']};
            padding: 1rem;
        }}
        
        /* Loading Spinner */
        .stSpinner > div {{
            border-top-color: {AWS_COLORS['primary_orange']} !important;
        }}
        
        /* Error/Warning/Info Messages */
        .stAlert {{
            border-radius: 6px;
        }}
        
        /* Scrollbar Styles */
        ::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        
        ::-webkit-scrollbar-track {{
            background: {AWS_COLORS['light_gray']};
        }}
        
        ::-webkit-scrollbar-thumb {{
            background: {AWS_COLORS['border_gray']};
            border-radius: 4px;
        }}
        
        ::-webkit-scrollbar-thumb:hover {{
            background: {AWS_COLORS['primary_orange']};
        }}
        
        /* Timestamp Styles */
        .message-timestamp {{
            font-size: 0.75rem;
            color: {AWS_COLORS['border_gray']};
            margin-top: 0.5rem;
            text-align: right;
        }}
        
        /* Empty State */
        .empty-state {{
            text-align: center;
            padding: 3rem;
            color: {AWS_COLORS['border_gray']};
        }}
        
        .empty-state-icon {{
            font-size: 3rem;
            margin-bottom: 1rem;
        }}
    </style>
    """
