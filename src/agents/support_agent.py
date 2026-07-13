"""support_agent.py — eComBot v3: PostgreSQL tools + persistent sessions + RAG.

This version keeps the Day 04 tool and session architecture intact and adds a
retrieval-augmented instruction provider that grounds factual product/support
questions in the local ChromaDB knowledge base.
"""

from __future__ import annotations

import logging
from pathlib import Path

import litellm
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.models.lite_llm import LiteLlm

from AgenticAI.ecombot.src.config.settings import settings
from AgenticAI.ecombot.src.rag.retriever import format_chunks, has_strong_match, retrieve
from AgenticAI.ecombot.src.tools.tools import TOOLS

litellm.suppress_debug_info = True
load_dotenv()

log = logging.getLogger(__name__)

_MODEL = "openrouter/google/gemini-2.5-flash"
_INSTRUCTION_FILE = Path(__file__).parent / "supporting_instruction_v4.txt"
_BASE_INSTRUCTION = _INSTRUCTION_FILE.read_text(encoding="utf-8").strip()

_GROUNDING_RULES = """
Knowledge base grounding rules:
- For product specifications, warranty coverage, shipping rules, return policy, refunds, and support FAQ questions, answer only from the retrieved knowledge base context below.
- If the retrieved context is empty or a weak match, do not guess. Say that the answer is not available in the current knowledge base and offer to help with product lookup, order status, cancellation, returns, shipping, or warranty questions.
- Do not invent prices, stock levels, delivery estimates, warranty terms, or policy details that are not explicitly supported by the retrieved text.
- If the user asks a live order question, use the existing order tools instead of relying on the knowledge base.
""".strip()

_FULL_BASE_INSTRUCTION = f"{_BASE_INSTRUCTION}\n\n{_GROUNDING_RULES}"


def _extract_query(ctx: ReadonlyContext) -> str:
    if not ctx.user_content or not ctx.user_content.parts:
        return ""
    return " ".join(part.text or "" for part in ctx.user_content.parts if part.text).strip()


def _grounding_block(query: str) -> str:
    if not query:
        return ""

    chunks = retrieve(query, n_results=settings.rag_top_k)
    if not has_strong_match(chunks):
        if chunks:
            top = chunks[0]
            log.info(
                "Weak KB retrieval for query=%r top_id=%s top_distance=%s threshold=%s",
                query,
                top.get("id"),
                top.get("distance"),
                settings.rag_similarity_threshold,
            )
        return (
            "Retrieved knowledge base context: NONE FOUND or below-confidence match for this question.\n"
            "Use the fallback rule above and say plainly that you do not have enough grounded information in the current knowledge base."
        )

    log.info(
        "Strong KB retrieval for query=%r top_id=%s top_distance=%s",
        query,
        chunks[0].get("id"),
        chunks[0].get("distance"),
    )
    return format_chunks(chunks)


def _build_instruction(ctx: ReadonlyContext) -> str:
    """InstructionProvider: run retrieval before every model turn."""
    query = _extract_query(ctx)
    if not query:
        return _FULL_BASE_INSTRUCTION
    return f"{_FULL_BASE_INSTRUCTION}\n\n{_grounding_block(query)}"


aria = LlmAgent(
    name="aria_day05",
    model=LiteLlm(model=_MODEL),
    instruction=_build_instruction,
    description=(
        "Day 05 eComBot: order lookup, cancellation, product search, persistent "
        "session state backed by Redis + PostgreSQL, and a RAG-grounded local "
        "knowledge base for product and support questions."
    ),
    tools=TOOLS,
)

