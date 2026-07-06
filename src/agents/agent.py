from google.adk.agents.llm_agent import Agent
from google.adk.models import LiteLlm
from pathlib import Path
from .order_tools import get_order_status, store_customer_name
import litellm
from dotenv import load_dotenv


_MODEL = "openrouter/openai/gpt-4o-mini"
_INSTRUCTION = (Path(__file__).parent / "supporting_instruction_v4.txt").read_text().strip()

support_agent = Agent(
    model=LiteLlm(model=_MODEL),
    name='support_agent',
    description='A helpful support assistant for user questions.',
    instruction=_INSTRUCTION,
    tools=[get_order_status,store_customer_name])

root_agent = support_agent
