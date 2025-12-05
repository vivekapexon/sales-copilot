"""
Mock Strategy Agent for Testing UI
Use this when the real strategy agent is unavailable due to dependency issues
"""

import json
import time


def run_strategy_agent(nlq: str):
    """
    Mock strategy agent that returns sample responses
    
    Args:
        nlq: Natural language query from user
        
    Returns:
        Mock agent response
    """
    # Simulate processing time
    time.sleep(1)
    
    # Detect query type and return appropriate mock response
    nlq_lower = nlq.lower()
    
    # Check for call objective / desired outcome queries
    if any(keyword in nlq_lower for keyword in ["objective", "outcome", "goal", "action", "desired", "priority", "main ask"]):
        return create_call_objective_response(nlq)
    # Check for pre-call brief
    elif "prepare" in nlq_lower or "brief" in nlq_lower or "ready" in nlq_lower:
        return create_full_brief_response(nlq)
    # Check for profile
    elif "profile" in nlq_lower or "who is" in nlq_lower or "about" in nlq_lower:
        return create_profile_response(nlq)
    # Check for prescribing
    elif "prescrib" in nlq_lower or "rx" in nlq_lower or "trend" in nlq_lower or "adoption" in nlq_lower:
        return create_prescribing_response(nlq)
    # Check for access
    elif "access" in nlq_lower or "formulary" in nlq_lower or "coverage" in nlq_lower or "copay" in nlq_lower:
        return create_access_response(nlq)
    # Check for history
    elif "history" in nlq_lower or "interaction" in nlq_lower or "last" in nlq_lower or "previous" in nlq_lower:
        return create_history_response(nlq)
    # Check for competitive
    elif "competitive" in nlq_lower or "competitor" in nlq_lower or "threat" in nlq_lower:
        return create_competitive_response(nlq)
    # Check for content
    elif "content" in nlq_lower or "material" in nlq_lower or "approved" in nlq_lower:
        return create_content_response(nlq)
    else:
        return create_generic_response(nlq)


def create_profile_response(nlq: str):
    """Mock Profile Agent response"""
    return {
        "Agent": "ProfileAgent",
        "HcpId": "H123",
        "Doctor Name": "Dr. John Smith",
        "Specialty": "Cardiology",
        "Practice Type": "Private Practice",
        "Years in Practice": 15,
        "Patient Volume": "High",
        "Note": "This is a MOCK response. Install strands to use real agent."
    }


def create_prescribing_response(nlq: str):
    """Mock Prescribing Agent response"""
    return {
        "Agent": "PrescribingAgent",
        "HcpId": "H123",
        "Doctor Name": "Dr. John Smith",
        "Specialty": "Cardiology",
        "Prescribing": {
            "Total Prescriptions (volume)": {
                "Last 7 days (trx_7d)": 45,
                "Last 28 days (trx_28d)": 180,
                "Last 90 days (trx_90d)": 540
            },
            "New Prescriptions (new_rx)": {
                "Last 7 days (nrx_7d)": 12,
                "Last 28 days (nrx_28d)": 48,
                "Last 90 days (nrx_90d)": 144
            },
            "Direction & Speed of change (momentum)": {
                "Week-Over-Week % Change": "+15%",
                "Quarter-Over-Quarter % Change": "+22%"
            },
            "Brand adoption journey": "Adopting"
        },
        "Note": "This is a MOCK response. Install strands to use real agent."
    }


def create_access_response(nlq: str):
    """Mock Access Agent response"""
    return {
        "Agent": "AccessAgent",
        "coverage_status": {
            "tier": 2,
            "prior_auth_requirement": "Some plans",
            "step_therapy_requirement": "None",
            "copay_median_usd": 35.0,
            "recent_change": "Win",
            "alert_severity": "Low"
        },
        "actionable_opportunities": [
            "Recent formulary win with BlueCross - emphasize improved access",
            "Copay assistance program available for high-deductible plans"
        ],
        "Note": "This is a MOCK response. Install strands to use real agent."
    }


def create_history_response(nlq: str):
    """Mock History Agent response"""
    return {
        "Agent": "HistoryAgent",
        "recent_interactions": [
            {
                "date": "2025-11-15",
                "type": "Phone Call",
                "duration": "15 minutes",
                "topics": ["Product efficacy", "Patient case discussion"],
                "objections": "None"
            },
            {
                "date": "2025-10-20",
                "type": "Office Visit",
                "duration": "30 minutes",
                "topics": ["Clinical trial results", "Dosing guidelines"],
                "objections": "Cost concerns"
            }
        ],
        "Note": "This is a MOCK response. Install strands to use real agent."
    }


def create_competitive_response(nlq: str):
    """Mock Competitive Agent response"""
    return {
        "Agent": "CompetitiveAgent",
        "text": "Moderate competitive pressure detected. Competitor X has increased sampling activity in the area by 20% over the last quarter. However, your brand maintains strong market share with this HCP.",
        "json": {
            "competitor_activity": "Moderate",
            "main_competitor": "Competitor X",
            "threat_level": "Medium",
            "share_trend": "Stable"
        },
        "Note": "This is a MOCK response. Install strands to use real agent."
    }


def create_content_response(nlq: str):
    """Mock Content Agent response"""
    return {
        "Agent": "ContentAgent",
        "text": "Based on this HCP's specialty and recent discussions, here are the recommended approved materials:",
        "json": {
            "recommended_materials": [
                {
                    "title": "Clinical Efficacy Overview",
                    "type": "PDF",
                    "relevance": "High",
                    "last_used": "Never"
                },
                {
                    "title": "Patient Case Studies",
                    "type": "Slide Deck",
                    "relevance": "High",
                    "last_used": "2025-10-20"
                },
                {
                    "title": "Safety Profile Summary",
                    "type": "PDF",
                    "relevance": "Medium",
                    "last_used": "Never"
                }
            ]
        },
        "Note": "This is a MOCK response. Install strands to use real agent."
    }


def create_call_objective_response(nlq: str):
    """Mock call objective recommendation response"""
    # Extract HCP ID if present
    import re
    hcp_match = re.search(r'HCP\s*(\d+)', nlq, re.IGNORECASE)
    hcp_id = hcp_match.group(1) if hcp_match else "1001"
    
    return {
        "Agent": "StrategyAgent",
        "HcpId": f"HCP{hcp_id}",
        "call_objective": {
            "primary_objective": "Increase adoption and prescribing volume",
            "desired_action": "Commit to prescribing for 2-3 new patients in the next month",
            "key_message": "Emphasize recent clinical trial results showing 30% improvement in patient outcomes",
            "rationale": "HCP is in 'Adopting' stage with positive momentum (+15% WoW growth). Recent formulary win with BlueCross provides strong access story.",
            "talking_points": [
                "Acknowledge recent prescribing growth and positive patient feedback",
                "Share new clinical data supporting efficacy in similar patient population",
                "Address any remaining access concerns with copay assistance program",
                "Provide patient starter kits and dosing guides"
            ],
            "potential_objections": [
                {
                    "objection": "Cost concerns",
                    "response": "Highlight recent formulary win and copay assistance program"
                },
                {
                    "objection": "Unfamiliarity with dosing",
                    "response": "Provide dosing guide and offer to connect with medical science liaison"
                }
            ],
            "success_metrics": [
                "Commitment to prescribe for 2-3 new patients",
                "Agreement to attend upcoming webinar on clinical data",
                "Request for patient education materials"
            ]
        },
        "supporting_intelligence": {
            "prescribing_trend": "Growing (+15% WoW)",
            "adoption_stage": "Adopting",
            "access_status": "Favorable (Tier 2, recent win)",
            "competitive_pressure": "Moderate",
            "last_interaction": "2025-11-15 (Phone Call)",
            "receptivity": "High"
        },
        "recommended_content": [
            "Clinical Efficacy Overview (PDF)",
            "Patient Case Studies (Slide Deck)",
            "Dosing Quick Reference Guide"
        ],
        "Note": "This is a MOCK response. Install strands to use real agent."
    }


def create_full_brief_response(nlq: str):
    """Mock full pre-call brief with multiple agents"""
    return [
        create_profile_response(nlq),
        create_prescribing_response(nlq),
        create_access_response(nlq),
        create_history_response(nlq),
        create_competitive_response(nlq),
        create_content_response(nlq),
        create_call_objective_response(nlq)
    ]


def create_generic_response(nlq: str):
    """Generic mock response"""
    return {
        "Agent": "MockAgent",
        "message": "I received your query but couldn't determine the specific intent.",
        "query": nlq,
        "suggestion": "Try asking about: profile, prescribing trends, access, history, competitive intel, or content recommendations",
        "Note": "This is a MOCK response. Install strands to use real agent."
    }
