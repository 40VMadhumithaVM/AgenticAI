from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from agent import support_agent

# In-memory session storage (required for state tracking across turns)
session_service = InMemorySessionService()

runner = Runner(
    agent=support_agent,
    session_service=session_service
)

if __name__ == "__main__":
    print("EcomBot is running...")
