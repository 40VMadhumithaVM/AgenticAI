"""Build and refresh the local eComBot knowledge base in ChromaDB.

Run from the repo root:
	python -m AgenticAI.ecombot.src.rag.embed_catalog

This script loads `data/products.json` and `data/faq.json`, splits the source
material into retrievable chunks, embeds each chunk with the configured OpenAI
embedding model, and upserts the result into the local ChromaDB collection.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import chromadb
import litellm
from dotenv import load_dotenv

from AgenticAI.ecombot.src.config.settings import settings

litellm.suppress_debug_info = True
load_dotenv()

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "data"


def _load_json(path: Path) -> list[dict[str, Any]]:
	with path.open("r", encoding="utf-8") as handle:
		payload = json.load(handle)
	if not isinstance(payload, list):
		raise ValueError(f"Expected a list in {path.name}")
	return payload


def _clean_text(value: Any) -> str:
	text = str(value or "").strip()
	return re.sub(r"\s+", " ", text)


def _join_list(values: Any) -> str:
	if not values:
		return ""
	if isinstance(values, list):
		return "; ".join(_clean_text(item) for item in values if _clean_text(item))
	return _clean_text(values)


def _product_chunks(product: dict[str, Any]) -> list[dict[str, Any]]:
	product_id = _clean_text(product.get("product_id"))
	name = _clean_text(product.get("product_name") or product.get("name") or product_id)
	category = _clean_text(product.get("category") or "Uncategorized")
	description = _clean_text(product.get("description"))
	shipping = _clean_text(product.get("shipping"))
	warranty = _clean_text(product.get("warranty"))

	price = product.get("price")
	currency = _clean_text(product.get("currency") or "USD")
	stock_qty = product.get("stock_qty")
	in_stock = product.get("in_stock")

	chunks: list[dict[str, Any]] = []

	if description:
		chunks.append(
			{
				"id": f"{product_id}_overview",
				"text": f"{name} ({product_id}) — {description}",
				"metadata": {
					"source_type": "product",
					"section": "overview",
					"product_id": product_id,
					"product_name": name,
					"category": category,
				},
			}
		)

	quick_facts: list[str] = [f"Category: {category}"]
	if price is not None:
		quick_facts.append(f"Price: {currency} {price}")
	if stock_qty is not None:
		quick_facts.append(f"Stock quantity: {stock_qty}")
	if in_stock is not None:
		quick_facts.append(f"In stock: {'Yes' if in_stock else 'No'}")

	chunks.append(
		{
			"id": f"{product_id}_pricing",
			"text": f"{name} pricing and availability — {'; '.join(quick_facts)}.",
			"metadata": {
				"source_type": "product",
				"section": "pricing",
				"product_id": product_id,
				"product_name": name,
				"category": category,
			},
		}
	)

	if shipping:
		chunks.append(
			{
				"id": f"{product_id}_shipping",
				"text": f"{name} shipping notes — {shipping}",
				"metadata": {
					"source_type": "product",
					"section": "shipping",
					"product_id": product_id,
					"product_name": name,
					"category": category,
				},
			}
		)

	if warranty:
		chunks.append(
			{
				"id": f"{product_id}_warranty",
				"text": f"{name} warranty — {warranty}",
				"metadata": {
					"source_type": "product",
					"section": "warranty",
					"product_id": product_id,
					"product_name": name,
					"category": category,
				},
			}
		)

	features = _join_list(product.get("features"))
	specs = product.get("specs") or {}
	if features or specs:
		spec_lines = [f"{name} feature summary"]
		if features:
			spec_lines.append(f"Features: {features}")
		if isinstance(specs, dict) and specs:
			spec_lines.append(
				"Specifications: "
				+ "; ".join(f"{_clean_text(key)}: {_clean_text(value)}" for key, value in specs.items())
			)
		chunks.append(
			{
				"id": f"{product_id}_details",
				"text": " — ".join(spec_lines),
				"metadata": {
					"source_type": "product",
					"section": "details",
					"product_id": product_id,
					"product_name": name,
					"category": category,
				},
			}
		)

	return chunks


def _faq_chunks(faq: dict[str, Any]) -> list[dict[str, Any]]:
	faq_id = _clean_text(faq.get("id"))
	category = _clean_text(faq.get("category") or "support")
	question = _clean_text(faq.get("question"))
	answer = _clean_text(faq.get("answer"))

	chunks: list[dict[str, Any]] = []

	if question:
		chunks.append(
			{
				"id": f"{faq_id}_question",
				"text": question,
				"metadata": {
					"source_type": "faq",
					"section": "question",
					"faq_id": faq_id,
					"category": category,
					"title": question,
				},
			}
		)

	if answer:
		chunks.append(
			{
				"id": f"{faq_id}_answer",
				"text": f"{question} — {answer}" if question else answer,
				"metadata": {
					"source_type": "faq",
					"section": "answer",
					"faq_id": faq_id,
					"category": category,
					"title": question or faq_id,
				},
			}
		)

	return chunks


def build_documents() -> list[dict[str, Any]]:
	"""Load source material and convert it into indexed document chunks."""
	products = _load_json(_DATA_DIR / "products.json")
	faqs = _load_json(_DATA_DIR / "faq.json")

	documents: list[dict[str, Any]] = []
	for product in products:
		documents.extend(_product_chunks(product))
	for faq in faqs:
		documents.extend(_faq_chunks(faq))

	return documents


def _embed_texts(texts: list[str]) -> list[list[float]]:
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise RuntimeError(
			"OPENAI_API_KEY is not set. Add it to .env before building the KB."
		)

	response = litellm.embedding(
		model=settings.rag_embedding_model,
		input=texts,
		api_key=api_key,
	)
	return [item["embedding"] for item in response.data]


def _get_collection():
	client = chromadb.PersistentClient(path=str(settings.rag_persist_path))
	try:
		client.delete_collection(name=settings.rag_collection_name)
	except Exception:
		pass
	return client.get_or_create_collection(name=settings.rag_collection_name)


def index_catalog() -> None:
	"""Refresh the local ChromaDB collection with the current knowledge base."""
	documents = build_documents()
	if not documents:
		raise RuntimeError("No knowledge-base documents were generated.")

	collection = _get_collection()
	embeddings = _embed_texts([doc["text"] for doc in documents])

	collection.upsert(
		ids=[doc["id"] for doc in documents],
		documents=[doc["text"] for doc in documents],
		metadatas=[doc["metadata"] for doc in documents],
		embeddings=embeddings,
	)

	print(
		f"Indexed {len(documents)} chunks into ChromaDB collection "
		f"'{settings.rag_collection_name}' at {settings.rag_persist_path} "
		f"using model '{settings.rag_embedding_model}'."
	)


if __name__ == "__main__":
	logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
	index_catalog()

