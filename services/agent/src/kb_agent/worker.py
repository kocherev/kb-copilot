import threading

from livekit.agents import Agent

SUPPORT_INSTRUCTIONS = (
    "Answer from the indexed knowledge base. "
    "Live sessions are not connected in this build."
)


def support_agent() -> Agent:
    return Agent(instructions=SUPPORT_INSTRUCTIONS)


def main() -> None:
    agent = support_agent()
    print(f"kb-support worker idle. {agent.instructions}", flush=True)
    threading.Event().wait()
