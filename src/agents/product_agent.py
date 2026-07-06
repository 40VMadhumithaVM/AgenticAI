from google.adk.agents.llm_agent import Agent
from google.adk.models import LiteLlm
from pathlib import Path

_MODEL = "openrouter/openai/gpt-4o-mini"

_PRODUCT_INSTRUCTION = """
You are a Product Agent.

Your responsibilities:
- Help users discover and compare products.
- Provide product details, features, and differences.
- Ask clarifying questions about budget, usage, and preferences when needed.
- Do NOT handle payments, orders, or pricing confirmations beyond general estimates.
- If a user request is about buying, redirect to Sales Agent mentally (do not mention internal routing).

Be accurate, structured, and concise.
"""

product_agent = Agent(
    model=LiteLlm(model=_MODEL),
    name="product_agent",
    description="Handles product discovery and comparisons.",
    instruction=_PRODUCT_INSTRUCTION
)
