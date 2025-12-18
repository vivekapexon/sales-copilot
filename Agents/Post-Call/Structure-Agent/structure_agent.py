import re
from strands import Agent,tool
import boto3
from typing import Dict, Any
s3 = boto3.client("s3")
bedrock = boto3.client("bedrock-runtime", region_name= "us-east-1")
import logging
from bedrock_agentcore.runtime import BedrockAgentCoreApp
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("compilance_agent")
s3_client = boto3.client("s3")
app = BedrockAgentCoreApp()

# Tokens considered placeholders / not useful
_PLACEHOLDER_TOKENS = {"[inaudible]", "[noise]", "[silence]", "[unintelligible]"}

NULL_OBJECT = {
    "call_sentiment_score": None,
    "sentiment_confidence": None,
    "receptivity_trend_90d_slope": None,
    "relationship_stage": None,
    "objection_intensity_index": None,
    "positive_to_negative_ratio": None,
    "next_call_risk_level": None,
    "notes_tone_summary": None,
    "data_available": False,
}

def _is_placeholder_only(text: str) -> bool:
    """Return True if text contains only placeholder tokens / punctuation / whitespace."""
    if not text or not text.strip():
        return True
    lower = text.strip().lower()
    # Strip common punctuation and numeric tokens
    stripped = re.sub(r"[^\w\[\]\s]", " ", lower)
    tokens = [t for t in re.split(r"\s+", stripped) if t]
    if not tokens:
        return True
    # If all tokens are in placeholder set or numeric / tiny
    meaningful = [t for t in tokens if t not in _PLACEHOLDER_TOKENS and len(t) > 1]
    return len(meaningful) == 0



@tool
def validate_transcription_for_sentiment(transcription_text: Optional[str]) -> Dict[str, Any]:#type:ignore
    """
    Validate transcription text for downstream Sentiment/Insight agent.

    Input:
        transcription_text: raw transcript string (may be None)

    Returns (dict):
    - If transcription is insufficient, returns the exact NULL_OBJECT (so agent LLM can return the null-object).
    - If transcription is sufficient, returns a dict:
        {
          "data_available": True,
          "transcription_text": "<original text trimmed>",
          "transcription_length_chars": <int>,
          "transcription_length_words": <int>,
          "placeholder_token_fraction": <float 0-1>
        }

    Important: This tool DOES NOT call any LLM/agent. It only validates/normalizes text.
    """
    # Normalize input
    if transcription_text is None:
        return NULL_OBJECT

    # convert to str and trim
    text = str(transcription_text).strip()

    # Quick length checks
    if len(text) < 30:
        return NULL_OBJECT

    # compute token stats
    words = [w for w in re.split(r"\s+", text) if w]
    word_count = len(words)
    char_count = len(text)

    # fraction of placeholder-like tokens
    lower_words = [w.strip().lower() for w in words]
    placeholder_count = sum(1 for w in lower_words if w in _PLACEHOLDER_TOKENS)
    placeholder_fraction = placeholder_count / max(1, word_count)

    # If more than 70% placeholder tokens -> insufficient
    if placeholder_fraction > 0.7 or _is_placeholder_only(text):
        return NULL_OBJECT

    # If after heuristics it's borderline short (<30 chars or <5 words) => insufficient
    if char_count < 30 or word_count < 5:
        return NULL_OBJECT

    # Passed checks -> return normalized metadata + transcription
    return {
        "data_available": True,
        "transcription_text": text,
        "transcription_length_chars": char_count,
        "transcription_length_words": word_count,
        "placeholder_token_fraction": round(placeholder_fraction, 3),
    }

# Define the agent
def create_call_structure_agent():

    return Agent(
    name="Sales Call Analyzer",
    system_prompt="""
You are Sales Call Analyzer, an elite sales-call intelligence system specializing in turning raw conversation transcripts into structured, actionable insights.

Your responsibilities:
Before performing ANY analysis, you MUST call the tool:
    validate_transcription_for_sentiment(transcription_text=<user transcript>)

1. ALWAYS call the validation tool FIRST, before doing any reasoning.    

2. ALWAYS load the transcription data first by calling Transcription Agent.
   - When a user asks to analyze a call or provides an transcription text
   - Use the provided JSON row data as the source of truth. Extract `transcript_text` as the primary transcript for analysis.
   - Incorporate contextual details from other fields (e.g., `territory_id`, `call_id`, `call_datetime_local`, `call_duration_minutes`, `structured_call_summary`, `key_topics_tags`, `objection_categories`, `compliance_redaction_flag`) to enrich your analysis and ensure relevance to the HCP's territory, history, and compliance needs.
   - Respect `compliance_redaction_flag`: If flagged, avoid referencing redacted content in outputs and note any limitations in the summary.

3. Extract structured insights
   After receiving the HCP rawtranscription text , parse it and analyze the `transcript_text` (enhancing with other row fields where relevant). Produce a JSON object with the following fields:

   {
     "hcp_id": "the provided HCP ID",
     "territory_id": "from row data",
     "call_id": "from row data",
     "call_datetime_local": "from row data",
     "call_duration_minutes": "from row data",
     "topics_discussed": ["pricing", "integration", "timeline"],
     "objections": [
       {"objection": "Too expensive", "response": "We can offer a discount", "category": "from objection_categories if matching"}
     ],
     "commitments": [
       {"who": "Rep", "commitment": "Send proposal", "due_date": "2025-04-05"}
     ],
     "follow_ups": [
       {"action": "Schedule demo", "owner": "Rep", "due_date": "next week"}
     ],
     "summary": "The customer showed strong interest... (tailored to HCP context, improving on structured_call_summary if present)",
     "key_topics_tags": "from row data (append or refine based on analysis)",
     "objection_categories": "from row data (update with new insights)",
     "compliance_notes": "Any compliance/redaction observations from analysis"
   }

   - If a field cannot be determined, use an empty list [] or null as appropriate. For summary, make it concise yet comprehensive (200-400 words), focusing on HCP-specific insights like engagement level, pain points tied to territory, and opportunities.
   - Be concise, factual, and base all insights strictly on the transcript text, augmented by row context.

4. Output rules
   - When returning analysis results to the user, OUTPUT ONLY valid JSON (no commentary, no markdown).
   - When invoking a tool, return only the tool invocation according to your agent/tool protocol.
   - Do not invent or hallucinate content—only extract and contextualize what is present.

5. Behavior & quality
   - Identify commitments, objections, next steps, pain points, and key themes, even when subtle. Cross-reference with `key_topics_tags` and `objection_categories` for accuracy.
   - When interpreting phrases like "next week" or "by Friday", infer reasonable absolute due dates only if asked; otherwise keep the original phrasing and optionally provide an inferred date as a separate field.
   - Provide speaker attribution when possible (e.g., "Rep" vs "HCP") inside commitments/follow_ups/objections.
   - Tailor insights to HCP context: E.g., reference territory-specific trends if inferable from row data.

Workflow (strict):
1 Call validate_transcription_for_sentiment()
2. Call Transcription Agent if you don't have trasnscription text.
3. Parse the returned JSON row, extract and analyze transcript_text with contextual fields
4. Return the enriched structured JSON

Remember: Valid JSON only. No additional text.
""",
    tools=[validate_transcription_for_sentiment]
)

agent=create_call_structure_agent()

# ---------------------------------------------------
#  Main Runner
# ---------------------------------------------------
@app.entrypoint
def run_main_agent(payload: dict = {}):
    # Example instruction: in real usage you can embed call_id / structured note JSON here.
    payload = payload.get("prompt","Provide structure called summary of my last call with HCP1001")
    agent_result = agent(payload)#type:ignore
    return agent_result

# ---------------------------------------------------
# Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()
    #run_main_agent()
