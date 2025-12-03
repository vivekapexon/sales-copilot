from __future__ import annotations
from strands import Agent, tool
from Tools.transcription_agent_tools import transcribe_audio

#
# ---------- Agents ----------
#
class TranscriptionAgent(Agent):
    def __init__(self):
        super().__init__(
            tools=[transcribe_audio],
            system_prompt=(
                "You are a transcription agent. Parse user instructions for transcription (s3/local path, "
                "output prefix, language, use_medical, media_format etc.). Call the transcribe_audio tool "
                "and return the tool's JSON output to the caller as JSON."
            )
        )

agent = TranscriptionAgent()
if __name__ == "__main__":
    
    # Use the agent by calling it with a user message
    result = agent("""Transcribe this audio:
local_audio_path=test.mp3
output_s3_prefix=s3://sales-copilot-bucket/transcripts/
language_code=en-US

                   """)
    print(result)