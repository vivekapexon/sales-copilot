# tools/validate_transcription_tool.py
import re
from typing import Dict, Any, Optional
from strands import tool

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
