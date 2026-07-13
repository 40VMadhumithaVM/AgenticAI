"""Compatibility wrapper for the Day 05 grounded support agent.

Existing demos still import `aria` from `agent.py`, so this module re-exports
the new RAG-enabled `support_agent.py` implementation without changing the
call sites.
"""

from AgenticAI.ecombot.src.agents.support_agent import aria

__all__ = ["aria"]
