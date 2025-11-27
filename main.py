# ---------------------------------------------------------------------------
# ENTRYPOINT SUMMARY
# ---------------------------------------------------------------------------
# This script builds the Supervisor Agent and executes a single routing run
# using a sample USER QUERY.
#
# ✔ build_supervisor() loads all sub-agent configurations and initializes
#   the SupervisorAgent instance.
#
# ✔ supervisor_agent.run(user_input=...) sends the user query through the
#   full Supervisor pipeline:
#       - LLM (or stub) determines the best sub-agent to call.
#       - Supervisor overrides the LLM 'input' and forwards the full user query.
#       - Selected sub-agent's tool is invoked with this full query.
#
# ✔ The final routing decision, selected agent, and mock tool output are printed.
#
# This block is mainly used for quick testing/debugging of:
#   - routing behavior
#   - agent selection
#   - JSON response structure
#   - input forwarding logic (full user query)
# ---------------------------------------------------------------------------
from Agents.supervisor_agent import build_supervisor
supervisor_agent=build_supervisor()


if __name__=="__main__":
    result=supervisor_agent.run(user_input="what are the  best cardiology in hcp")
    print(result)
