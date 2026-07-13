"""Query the local eComBot knowledge base in ChromaDB.

The retriever uses the same OpenAI embedding model as the indexer and returns
the closest matching chunks with their metadata and distances. Callers can use
the distance information to decide whether retrieval is strong enough to trust
or whether they should fall back to a safe no-answer response.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

import chromadb
import litellm
from dotenv import load_dotenv

from AgenticAI.ecombot.src.config.settings import settings

litellm.suppress_debug_info = True
load_dotenv()

log = logging.getLogger(__name__)


def _embed_text(text: str) -> list[float]:
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise RuntimeError(
			"OPENAI_API_KEY is not set. Add it to .env before querying the KB."
		)

	response = litellm.embedding(
		model=settings.rag_embedding_model,
		input=[text],
		api_key=api_key,
	)
	return response.data[0]["embedding"]


@lru_cache(maxsize=1)
def _get_collection():
	client = chromadb.PersistentClient(path=str(settings.rag_persist_path))
	return client.get_or_create_collection(name=settings.rag_collection_name)


def retrieve(query: str, n_results: int = 3) -> list[dict[str, Any]]:
	"""Return the best-matching knowledge chunks for a query.

	Each result contains the chunk ID, text, metadata, distance, and a simple
	similarity score. The list is empty if the query is empty, the collection is
	empty, or retrieval fails.
	"""
	if not query or not query.strip():
		return []

	try:
		collection = _get_collection()
		count = collection.count()
		if count == 0:
			log.warning(
				"ChromaDB collection '%s' is empty — run embed_catalog.py first",
				settings.rag_collection_name,
			)
			return []

		embedding = _embed_text(query.strip())
		result = collection.query(
			query_embeddings=[embedding],
			n_results=min(n_results, count),
		)
	except Exception as exc:
		log.warning("Knowledge-base retrieval failed: %s", exc)
		return []

	ids = (result.get("ids") or [[]])[0]
	documents = (result.get("documents") or [[]])[0]
	metadatas = (result.get("metadatas") or [[]])[0]
	distances = (result.get("distances") or [[]])[0]

	chunks: list[dict[str, Any]] = []
	for doc_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
		score = max(0.0, 1.0 - float(distance or 0.0))
		chunks.append(
			{
				"id": doc_id,
				"text": text,
				"metadata": metadata or {},
				"distance": float(distance) if distance is not None else None,
				"score": score,
			}
		)

	return chunks


def has_strong_match(chunks: list[dict[str, Any]]) -> bool:
	"""Return True when the retrieval result is strong enough to trust."""
	if not chunks:
		return False
	top_distance = chunks[0].get("distance")
	if top_distance is None:
		return False
	return float(top_distance) <= settings.rag_similarity_threshold


def format_chunks(chunks: list[dict[str, Any]]) -> str:
	"""Format retrieved chunks for logging or prompt injection."""
	if not chunks:
		return (
			"Retrieved knowledge base context: NONE FOUND.\n"
			"Use the fallback rule and do not guess unsupported facts."
		)

	lines = [
		"Retrieved knowledge base context (use this as the only factual source for the answer):"
	]
	for chunk in chunks:
		metadata = chunk.get("metadata") or {}
		section = metadata.get("section", "chunk")
		source_type = metadata.get("source_type", "kb")
		label_bits = [chunk["id"], source_type, section]
		if metadata.get("product_name"):
			label_bits.append(metadata["product_name"])
		if metadata.get("title"):
			label_bits.append(metadata["title"])
		header = " / ".join(str(bit) for bit in label_bits if bit)
		lines.append(f"- [{header}] {chunk['text']}")
	return "\n".join(lines)

