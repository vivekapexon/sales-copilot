# /post_call/Agents/sentiment_agent.py
import re
from typing import Dict, Any, Optional
from strands import tool
import logging
from strands import Agent,tool

from bedrock_agentcore.runtime import BedrockAgentCoreApp
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sentiment_agent")
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
def validate_transcription_for_sentiment(transcription_text: Optional[str]) -> Dict[str, Any]:
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


INSIGHT_EXTRACTION_AGENT_PROMPT = """
You are the Sentiment and Insight Extraction Agent for HCP sales calls.
Before performing ANY analysis, you MUST call the tool:
    validate_transcription_for_sentiment(transcription_text=<user transcript>)

RULES (NON-NEGOTIABLE):
1. ALWAYS call the validation tool FIRST, before doing any reasoning.
2. NEVER analyze raw user text directly.
3. After calling the tool:
   - If the tool returns { "data_available": false, ... }:
       → You MUST IMMEDIATELY return that exact null-object as your final output.
       → DO NOT modify, rewrite, or add anything.
       → DO NOT attempt sentiment analysis.
   - If the tool returns { "data_available": true, "transcription_text": "..." }:
       → Use ONLY the returned `transcription_text` for analysis.
       → Ignore the user’s original transcript string.
4. Output must be EXACTLY one JSON object. No explanation, no notes, no assistant text.

------------------------------------------------------------
AFTER VALIDATION TOOL RETURNS data_available = true:
------------------------------------------------------------

Now perform sentiment/insight extraction STRICTLY according to these rules:

Required output JSON fields:
{
  "call_sentiment_score": <float 0.0–1.0 or null>,
  "sentiment_confidence": <float 0.0–1.0 or null>,
  "receptivity_trend_90d_slope": <float or null>,
  "relationship_stage": <"Champion" | "Adopter" | "Prospect" | "At-risk" | null>,
  "objection_intensity_index": <float 0.0–1.0 or null>,
  "positive_to_negative_ratio": <float >= 0 or null>,
  "next_call_risk_level": <"low" | "medium" | "high" | null>,
  "notes_tone_summary": <
        "neutral and time-constrained" |
        "optimistic and collaborative" |
        "cautiously positive with access concerns" |
        null
  >
}

STRICT RULES:
- Produce ONLY ONE JSON OBJECT.
- NO extra keys.
- NO prose, NO commentary.
- If you are unsure of a field, set it to null.
- Round floats:
    • sentiment_score → 2 decimals
    • sentiment_confidence → 2 decimals
    • objection_intensity_index → 2 decimals
    • positive_to_negative_ratio → 2 decimals
    • receptivity_trend_90d_slope → 3 decimals
- DO NOT fabricate historical context. If not in transcript → null.
- DO NOT hallucinate content.

------------------------------------------------------------
NULL-OBJECT CASE (MANDATORY)
------------------------------------------------------------
If validation tool indicates insufficient text, return EXACTLY:

{
  "call_sentiment_score": null,
  "sentiment_confidence": null,
  "receptivity_trend_90d_slope": null,
  "relationship_stage": null,
  "objection_intensity_index": null,
  "positive_to_negative_ratio": null,
  "next_call_risk_level": null,
  "notes_tone_summary": null,
  "data_available": false
}

This must be returned with no additional text.

------------------------------------------------------------
EXECUTION SEQUENCE (MANDATORY)
------------------------------------------------------------
1. Call validate_transcription_for_sentiment()
2. Inspect tool result:
   - If data_available=false → return null-object exactly.
   - If data_available=true  → extract `transcription_text` and analyze it.
3. Produce EXACT one JSON object as defined.

You must ALWAYS follow this sequence.
"""

def create_sentiment_agent() -> Agent:
    return Agent(
    name="Sentiment and Insight Extraction Agent",
    system_prompt=INSIGHT_EXTRACTION_AGENT_PROMPT,

    tools=[validate_transcription_for_sentiment]

)

agent=create_sentiment_agent()


@app.entrypoint
def run_main_agent(payload: dict = {}):
    query_transcript="""Rep: Hello Dr. Thomas, I appreciate you meeting with me.
            HCP: Thanks, let's keep it brief clinic is busy today.
            Rep: I'd like to focus on real-world outcomes in high-risk cohorts and safety monitoring and lab follow-up best practices today.
            HCP: Okay please highlight what's changed.
            Rep: Based on recent updates, the KOL webinar summarized patient selection criteria effectively. Also, I can provide templates for PA.
            HCP: No specific concerns today just curious about the updates.
            Rep: I'll share the new coverage sheet and schedule a quick follow-up demo.
            HCP: Great email the checklists and we'll trial with a patient this week."""


    payload = payload.get("prompt",query_transcript)
    agent_result = agent(payload)#type:ignore
    return agent_result
# ---------------------------------------------------
# Run Locally
# ---------------------------------------------------
if __name__ == "__main__":
    app.run()
    #run_main_agent()