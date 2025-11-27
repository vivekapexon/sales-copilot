
from typing import List, Dict, Any, Optional
from strands import Agent
from tools.strategy_agent_tools import * # import all realted tools

# Agent wrapper
def _tools_list():
    return [load_kb_metadata, synthesize_brief, persist_brief]


Strategy_agent = Agent(
    system_prompt="""
You are a regulated sales assistant. Use ONLY the provided structured inputs and the explicitly linked evidence to produce a short, actionable Pre-Call Brief for a field representative. Always include evidence source_ids for every factual claim or recommendation. Do NOT invent facts or cite sources not in the input. If critical inputs are missing, list them and give a conservative fallback. Output ONLY valid JSON conforming to the Brief schema.
""",
    tools=_tools_list(),
)

def run_strategy_agent(agent_outputs: List[Dict[str, Any]], kb_s3_url: Optional[str] = None, brief_id: Optional[str] = None):
    """
    Orchestration helper to run the agent end-to-end:
     1) load kb metadata
     2) synthesize brief
     3) persist brief
    """
    kb_ctx = load_kb_metadata(kb_s3_url=kb_s3_url)
    brief = synthesize_brief(agent_outputs=agent_outputs, kb_context=kb_ctx, brief_id=brief_id)
    persist_info = persist_brief(brief)
    return {"brief": brief, "persist_info": persist_info}
