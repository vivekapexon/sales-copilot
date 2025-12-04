import json
from strands import Agent,tool
from Tools.validate_transcription_tools import validate_transcription_for_sentiment

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

sentiment_agent = Agent(
    name="Sentiment and Insight Extraction Agent",
    system_prompt=INSIGHT_EXTRACTION_AGENT_PROMPT,

    tools=[validate_transcription_for_sentiment]

)

if __name__ == "__main__":
    # Example usage
    query_transcript="""Rep: Hello Dr. Thomas, I appreciate you meeting with me.
            HCP: Thanks, let's keep it brief clinic is busy today.
            Rep: I'd like to focus on real-world outcomes in high-risk cohorts and safety monitoring and lab follow-up best practices today.
            HCP: Okay please highlight what's changed.
            Rep: Based on recent updates, the KOL webinar summarized patient selection criteria effectively. Also, I can provide templates for PA.
            HCP: No specific concerns today just curious about the updates.
            Rep: I'll share the new coverage sheet and schedule a quick follow-up demo.
            HCP: Great email the checklists and we'll trial with a patient this week."""


    sentiment_agent(query_transcript)
