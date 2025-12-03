"""
Simple SALES-COPILOT App (No Chat History)
Direct integration with Strategy Agent
"""

import streamlit as st
import sys
import os

# Add Strategy-Agent to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'Strategy-Agent'))

# Try to import the real agent
try:
    from strategy_agent import run_strategy_agent
    USING_REAL_AGENT = True
    st.success("✓ Using REAL Strategy Agent")
except ImportError as e:
    from mock_strategy_agent import run_strategy_agent
    USING_REAL_AGENT = False
    st.warning(f"⚠️ Using Mock Agent - strands error: {e}")

# AWS Colors
AWS_ORANGE = "#FF9900"
AWS_DARK = "#232F3E"

# Page config
st.set_page_config(
    page_title="SALES-COPILOT",
    page_icon="🤖",
    layout="wide"
)

# Custom CSS
st.markdown(f"""
<style>
    .main-header {{
        background: linear-gradient(90deg, {AWS_DARK} 0%, #37475A 100%);
        color: white;
        padding: 1.5rem;
        border-bottom: 4px solid {AWS_ORANGE};
        text-align: center;
        font-size: 2rem;
        font-weight: bold;
        margin: -1rem -1rem 2rem -1rem;
    }}
</style>
""", unsafe_allow_html=True)

# Header
st.markdown(f'<div class="main-header"><span style="color: {AWS_ORANGE}">SALES</span>-COPILOT</div>', unsafe_allow_html=True)

# Main interface
st.write("### Ask me anything about HCPs, prescribing trends, or get pre-call briefs!")

# Input
user_query = st.text_input("Your question:", placeholder="e.g., Show me details of HCP1005")

if st.button("Submit", type="primary") or user_query:
    if user_query:
        with st.spinner("🤖 Agent is processing..."):
            try:
                # Call the agent
                response = run_strategy_agent(user_query)
                
                # Display response
                st.write("### Response:")
                
                # Format response based on type
                if isinstance(response, dict):
                    st.json(response)
                elif isinstance(response, list):
                    for item in response:
                        st.json(item)
                        st.divider()
                else:
                    st.write(response)
                    
            except Exception as e:
                st.error(f"Error: {e}")
                st.write("Please check that all agents are properly configured.")

# Sidebar with info
with st.sidebar:
    st.write("### Agent Status")
    if USING_REAL_AGENT:
        st.success("✓ Real Strategy Agent")
    else:
        st.warning("⚠️ Mock Agent")
        st.write("To use real agent:")
        st.code("1. Install VC++ Redistributable\n2. Restart computer\n3. pip install strands --no-cache-dir")
    
    st.divider()
    st.write("### Example Queries")
    st.code("""
- Show me details of HCP1005
- Give me profile for HCP H123
- What are prescribing trends?
- Prepare me for call with Dr. Smith
- Show access intelligence
- What's the call objective?
    """)
