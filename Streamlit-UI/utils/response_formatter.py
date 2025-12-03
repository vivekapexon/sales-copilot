"""
Response Formatter Module
Formats agent responses for display in the UI
"""

import json
from typing import Dict, Any, Union


def format_agent_response(response: Union[Dict, str]) -> str:
    """
    Format agent response for display
    
    Args:
        response: Agent response (dict or string)
        
    Returns:
        HTML-formatted string for display
    """
    if isinstance(response, str):
        return response
    
    if not isinstance(response, dict):
        return str(response)
    
    # Check response type
    response_type = response.get('type', 'unknown')
    
    if response_type == 'text':
        return response.get('content', '')
    elif response_type == 'multi_agent':
        return format_multi_agent_response(response.get('agents', []))
    else:
        # Check if it's a single agent response
        if 'Agent' in response:
            agent_name = response.get('Agent', 'Unknown Agent')
            return format_single_agent_response(agent_name, response)
        else:
            # Generic JSON formatting
            return format_json_response(response)


def format_single_agent_response(agent_name: str, data: Dict) -> str:
    """
    Format a single agent's response
    
    Args:
        agent_name: Name of the agent
        data: Agent response data
        
    Returns:
        HTML-formatted string
    """
    # Remove 'Agent' key from data for display
    display_data = {k: v for k, v in data.items() if k != 'Agent'}
    
    # Format based on agent type
    if agent_name == "ProfileAgent":
        return format_profile_agent_response(display_data)
    elif agent_name == "PrescribingAgent":
        return format_prescribing_agent_response(display_data)
    elif agent_name == "AccessAgent":
        return format_access_agent_response(display_data)
    elif agent_name == "HistoryAgent":
        return format_history_agent_response(display_data)
    elif agent_name == "CompetitiveAgent":
        return format_competitive_agent_response(display_data)
    elif agent_name == "ContentAgent":
        return format_content_agent_response(display_data)
    elif agent_name == "StrategyAgent":
        return format_strategy_agent_response(display_data)
    elif agent_name == "MockAgent":
        return format_mock_agent_response(display_data)
    else:
        return f"<strong>{agent_name}</strong><br><pre>{json.dumps(display_data, indent=2)}</pre>"


def format_multi_agent_response(agents: list) -> str:
    """
    Format response from multiple agents
    
    Args:
        agents: List of agent responses
        
    Returns:
        HTML-formatted string
    """
    formatted_parts = []
    
    for agent_data in agents:
        if isinstance(agent_data, dict) and 'Agent' in agent_data:
            agent_name = agent_data['Agent']
            formatted_parts.append(format_single_agent_response(agent_name, agent_data))
        else:
            formatted_parts.append(format_json_response(agent_data))
    
    return "<hr>".join(formatted_parts)


def format_profile_agent_response(data: Dict) -> str:
    """Format Profile Agent response"""
    html = "<strong>👤 Profile Agent</strong><br><br>"
    
    # Format key profile information
    if 'HcpId' in data:
        html += f"<strong>HCP ID:</strong> {data['HcpId']}<br>"
    if 'Doctor Name' in data:
        html += f"<strong>Name:</strong> {data['Doctor Name']}<br>"
    if 'Specialty' in data:
        html += f"<strong>Specialty:</strong> {data['Specialty']}<br>"
    
    # Add remaining data as JSON
    remaining_data = {k: v for k, v in data.items() 
                     if k not in ['HcpId', 'Doctor Name', 'Specialty']}
    
    if remaining_data:
        html += f"<br><details><summary>View Details</summary><pre>{json.dumps(remaining_data, indent=2)}</pre></details>"
    
    return html


def format_prescribing_agent_response(data: Dict) -> str:
    """Format Prescribing Agent response"""
    html = "<strong>💊 Prescribing Agent</strong><br><br>"
    
    # Format header info
    if 'HcpId' in data:
        html += f"<strong>HCP ID:</strong> {data['HcpId']}<br>"
    if 'Doctor Name' in data:
        html += f"<strong>Name:</strong> {data['Doctor Name']}<br>"
    if 'Specialty' in data:
        html += f"<strong>Specialty:</strong> {data['Specialty']}<br><br>"
    
    # Format prescribing data
    if 'Prescribing' in data:
        prescribing = data['Prescribing']
        html += "<strong>Prescribing Metrics:</strong><br>"
        html += f"<pre>{json.dumps(prescribing, indent=2)}</pre>"
    else:
        # Show all data
        remaining_data = {k: v for k, v in data.items() 
                         if k not in ['HcpId', 'Doctor Name', 'Specialty']}
        html += f"<pre>{json.dumps(remaining_data, indent=2)}</pre>"
    
    return html


def format_access_agent_response(data: Dict) -> str:
    """Format Access Agent response"""
    html = "<strong>🔐 Access Agent</strong><br><br>"
    
    # Format coverage status
    if 'coverage_status' in data:
        coverage = data['coverage_status']
        html += "<strong>Coverage Status:</strong><br>"
        html += f"<pre>{json.dumps(coverage, indent=2)}</pre><br>"
    
    # Format actionable opportunities
    if 'actionable_opportunities' in data:
        opportunities = data['actionable_opportunities']
        html += "<strong>Actionable Opportunities:</strong><ul>"
        for opp in opportunities:
            html += f"<li>{opp}</li>"
        html += "</ul>"
    
    # Add remaining data
    remaining_data = {k: v for k, v in data.items() 
                     if k not in ['coverage_status', 'actionable_opportunities']}
    if remaining_data:
        html += f"<details><summary>Additional Details</summary><pre>{json.dumps(remaining_data, indent=2)}</pre></details>"
    
    return html


def format_history_agent_response(data: Dict) -> str:
    """Format History Agent response"""
    html = "<strong>📋 History Agent</strong><br><br>"
    html += f"<pre>{json.dumps(data, indent=2)}</pre>"
    return html


def format_competitive_agent_response(data: Dict) -> str:
    """Format Competitive Agent response"""
    html = "<strong>⚔️ Competitive Agent</strong><br><br>"
    
    # Check for text field
    if 'text' in data:
        html += f"<p>{data['text']}</p>"
    
    # Check for json field
    if 'json' in data:
        html += f"<details><summary>View Details</summary><pre>{json.dumps(data['json'], indent=2)}</pre></details>"
    else:
        # Show all data
        remaining_data = {k: v for k, v in data.items() if k != 'text'}
        if remaining_data:
            html += f"<pre>{json.dumps(remaining_data, indent=2)}</pre>"
    
    return html


def format_content_agent_response(data: Dict) -> str:
    """Format Content Agent response"""
    html = "<strong>📄 Content Agent</strong><br><br>"
    
    # Check for text field
    if 'text' in data:
        html += f"<p>{data['text']}</p>"
    
    # Check for json field
    if 'json' in data:
        html += f"<details><summary>View Details</summary><pre>{json.dumps(data['json'], indent=2)}</pre></details>"
    else:
        # Show all data
        remaining_data = {k: v for k, v in data.items() if k != 'text'}
        if remaining_data:
            html += f"<pre>{json.dumps(remaining_data, indent=2)}</pre>"
    
    return html


def format_strategy_agent_response(data: Dict) -> str:
    """Format Strategy Agent (Call Objective) response"""
    html = "<strong>🎯 Call Objective & Strategy</strong><br><br>"
    
    # Format HCP ID
    if 'HcpId' in data:
        html += f"<strong>HCP:</strong> {data['HcpId']}<br><br>"
    
    # Format call objective
    if 'call_objective' in data:
        obj = data['call_objective']
        
        html += "<div style='background-color: #FFF3CD; padding: 1rem; border-radius: 8px; border-left: 4px solid #FF9900; margin: 1rem 0;'>"
        html += f"<h4 style='margin-top: 0; color: #232F3E;'>📌 Primary Objective</h4>"
        html += f"<p style='font-size: 1.1rem; font-weight: bold;'>{obj.get('primary_objective', 'N/A')}</p>"
        html += f"<p><strong>Desired Action:</strong> {obj.get('desired_action', 'N/A')}</p>"
        html += "</div>"
        
        # Key message
        if 'key_message' in obj:
            html += f"<p><strong>💬 Key Message:</strong><br>{obj['key_message']}</p>"
        
        # Rationale
        if 'rationale' in obj:
            html += f"<p><strong>📊 Rationale:</strong><br>{obj['rationale']}</p>"
        
        # Talking points
        if 'talking_points' in obj:
            html += "<p><strong>🗣️ Talking Points:</strong></p><ul>"
            for point in obj['talking_points']:
                html += f"<li>{point}</li>"
            html += "</ul>"
        
        # Potential objections
        if 'potential_objections' in obj:
            html += "<p><strong>⚠️ Potential Objections & Responses:</strong></p>"
            for objection in obj['potential_objections']:
                html += f"<div style='background-color: #F8F9FA; padding: 0.5rem; margin: 0.5rem 0; border-radius: 4px;'>"
                html += f"<strong>Objection:</strong> {objection.get('objection', 'N/A')}<br>"
                html += f"<strong>Response:</strong> {objection.get('response', 'N/A')}"
                html += "</div>"
        
        # Success metrics
        if 'success_metrics' in obj:
            html += "<p><strong>✅ Success Metrics:</strong></p><ul>"
            for metric in obj['success_metrics']:
                html += f"<li>{metric}</li>"
            html += "</ul>"
    
    # Supporting intelligence
    if 'supporting_intelligence' in data:
        intel = data['supporting_intelligence']
        html += "<details><summary><strong>📈 Supporting Intelligence</strong></summary>"
        html += f"<pre>{json.dumps(intel, indent=2)}</pre>"
        html += "</details>"
    
    # Recommended content
    if 'recommended_content' in data:
        content = data['recommended_content']
        html += "<p><strong>📄 Recommended Content:</strong></p><ul>"
        for item in content:
            html += f"<li>{item}</li>"
        html += "</ul>"
    
    # Add note if present
    if 'Note' in data:
        html += f"<p style='color: #856404; background-color: #FFF3CD; padding: 0.5rem; border-radius: 4px; margin-top: 1rem;'><em>{data['Note']}</em></p>"
    
    return html


def format_mock_agent_response(data: Dict) -> str:
    """Format Mock Agent response"""
    html = "<strong>🤖 Mock Agent</strong><br><br>"
    
    if 'message' in data:
        html += f"<p>{data['message']}</p>"
    
    if 'suggestion' in data:
        html += f"<p><strong>💡 Suggestion:</strong> {data['suggestion']}</p>"
    
    if 'query' in data:
        html += f"<p><em>Your query: {data['query']}</em></p>"
    
    if 'Note' in data:
        html += f"<p style='color: #856404; background-color: #FFF3CD; padding: 0.5rem; border-radius: 4px; margin-top: 1rem;'><em>{data['Note']}</em></p>"
    
    return html


def format_json_response(data: Dict) -> str:
    """
    Format generic JSON response
    
    Args:
        data: Dictionary to format
        
    Returns:
        HTML-formatted string with syntax-highlighted JSON
    """
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    return f"<pre>{json_str}</pre>"
