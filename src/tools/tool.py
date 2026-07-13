"""
tools.py — eComBot v2 tools backed by PostgreSQL
=================================================
Day 04: Real tools that query PostgreSQL and update session state.

Tools:
    - get_order_status(order_id)     → Look up an order
    - cancel_order(order_id)         → Cancel a confirmed order
    - lookup_product(product_name)   → Search products by name or ID
    - save_customer_name(customer_name)       → Store customer name in session
    - get_session_summary()          → Return current session context

Session state keys (persisted via Redis-backed session service):
    - current_order_id
    - current_customer_name
    - current_product_id
    - last_intent
    - last_lookup_key
"""

import logging
import re
from typing import Any

from google.adk.tools import ToolContext

from db import query_one, query_all, execute

log = logging.getLogger(__name__)

# ── Validation patterns ───────────────────────────────────────────────────
_ORDER_ID_PATTERN = re.compile(r"^ORD-\d{3,}$", re.IGNORECASE)
_PRODUCT_ID_PATTERN = re.compile(r"^PR-\d{3,}$", re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 1: get_order_status
# ═══════════════════════════════════════════════════════════════════════════
def get_order_status(order_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """
    Look up the status of an order by ID.

    If order_id is "current", uses the last order stored in session state.

    Args:
        order_id: Order ID like "ORD-001", or "current" to use session context.

    Returns:
        Order details or an error message.
    """
    # ① Resolve "current" from session state
    if order_id.lower() == "current":
        order_id = tool_context.state.get("order_id", "")
        if not order_id:
            return {"error": "No order in context. Please provide an order ID."}

    # ② Validate format
    if not _ORDER_ID_PATTERN.match(order_id):
        return {
            "error": f"Invalid order ID format: '{order_id}'. Expected format: ORD-XXX"
        }

    order_id = order_id.upper()

    # ③ Query PostgreSQL
    try:
        row = query_one(
            """
            SELECT order_id, customer_name, product_id, product_name,
                   stock, price_usd, status, delivery_date
            FROM orders
            WHERE order_id = %s
            """,
            (order_id,),
        )
    except Exception as exc:
        log.exception("DB error in get_order_status: %s", exc)
        return {"error": "Unable to reach order system. Please try again."}

    if not row:
        return {"error": f"Order {order_id} not found."}

    # ④ Update session state (Redis-backed)
    tool_context.state["order_id"] = order_id
    tool_context.state["last_intent"] = "order_lookup"
    tool_context.state["last_lookup_key"] = order_id

    log.info("Order lookup: %s → %s", order_id, row["status"])

    return {
        "order_id": row["order_id"],
        "customer_name": row["customer_name"],
        "product_id": row["product_id"],
        "product_name": row["product_name"],
        "stock": row["stock"],
        "price_usd": float(row["price_usd"]) if row["price_usd"] else 0.0,
        "status": row["status"],
        "delivery_date": str(row["delivery_date"]) if row["delivery_date"] else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 2: cancel_order
# ═══════════════════════════════════════════════════════════════════════════
def cancel_order(order_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """
    Cancel a confirmed order.

    Only orders in 'confirmed' or 'processing' status can be cancelled.
    Delivered or already-cancelled orders return an error.

    Args:
        order_id: Order ID like "ORD-001", or "current" to use session context.

    Returns:
        Cancellation confirmation or error message.
    """
    # ① Resolve "current" from session state
    if order_id.lower() == "current":
        order_id = tool_context.state.get("order_id", "")
        if not order_id:
            return {"error": "No order in context. Please provide an order ID."}

    # ② Validate format
    if not _ORDER_ID_PATTERN.match(order_id):
        return {"error": f"Invalid order ID format: '{order_id}'"}

    order_id = order_id.upper()

    # ③ Check current status first
    try:
        row = query_one(
            "SELECT order_id, status FROM orders WHERE order_id = %s",
            (order_id,),
        )
    except Exception as exc:
        log.exception("DB error in cancel_order (check): %s", exc)
        return {"error": "Unable to reach order system. Please try again."}

    if not row:
        return {"error": f"Order {order_id} not found."}

    current_status = (row["status"] or "").lower()

    # ④ Business rules — check if cancellable
    if current_status == "cancelled":
        return {
            "order_id": order_id,
            "status": "already_cancelled",
            "message": f"Order {order_id} is already cancelled.",
        }

    if current_status == "delivered":
        return {
            "order_id": order_id,
            "status": "cannot_cancel",
            "message": f"Order {order_id} has been delivered and cannot be cancelled.",
        }

    # ⑤ Perform cancellation
    try:
        execute(
            """
            UPDATE orders
            SET status = 'cancelled', updated_at = NOW()
            WHERE order_id = %s
            """,
            (order_id,),
        )
    except Exception as exc:
        log.exception("DB error in cancel_order (update): %s", exc)
        return {"error": "Failed to cancel the order. Please try again."}

    # ⑥ Update session state
    tool_context.state["current_order_id"] = order_id
    tool_context.state["last_intent"] = "order_cancel"

    log.info("Order cancelled: %s", order_id)

    return {
        "order_id": order_id,
        "status": "cancelled",
        "message": f"Order {order_id} has been successfully cancelled.",
    }


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 3: lookup_product
# ═══════════════════════════════════════════════════════════════════════════
def lookup_product(product_name: str, tool_context: ToolContext) -> dict[str, Any]:
    """
    Search for products by name or product ID.

    Supports:
        - Exact product ID lookup (e.g., "PRD-101")
        - Case-insensitive name search (e.g., "iphone")

    Args:
        product_name: Product name (partial match) or product ID.

    Returns:
        Product details or list of matching products.
    """
    # ① Validate input
    if not product_name or not product_name.strip():
        return {"error": "Please provide a product name or ID to search for."}

    product_name = product_name.strip()

    try:
        # ② Route: Product ID vs. name search
        if _PRODUCT_ID_PATTERN.match(product_name):
            # Exact ID lookup
            product_id = product_name.upper()
            row = query_one(
                """
                SELECT product_id, name, description, category,
                       price, stock_quantity, is_active
                FROM products
                WHERE product_id = %s
                """,
                (product_id,),
            )

            if not row:
                return {"error": f"Product {product_id} not found."}

            # Update session state
            tool_context.state["current_product_id"] = product_id
            tool_context.state["last_intent"] = "product_lookup"
            tool_context.state["last_lookup_key"] = product_id

            log.info("Product lookup by ID: %s", product_id)

            return _format_product(row)

        else:
            # Name-based fuzzy search
            rows = query_all(
                """
                SELECT product_id, name, description, category,
                       price, stock_quantity, is_active
                FROM products
                WHERE LOWER(name) LIKE %s
                   OR LOWER(description) LIKE %s
                ORDER BY name
                LIMIT 5
                """,
                (f"%{product_name.lower()}%", f"%{product_name.lower()}%"),
            )

            if not rows:
                return {
                    "error": f"No products found matching '{product_name}'."
                }

            # Update session state
            tool_context.state["last_intent"] = "product_search"
            tool_context.state["last_lookup_key"] = product_name

            # If single result, treat as selection
            if len(rows) == 1:
                tool_context.state["current_product_id"] = rows[0]["product_id"]

            log.info("Product search: '%s' → %d results", product_name, len(rows))

            return {
                "query": product_name,
                "count": len(rows),
                "products": [_format_product(r) for r in rows],
            }

    except Exception as exc:
        log.exception("DB error in lookup_product: %s", exc)
        return {"error": "Unable to search products. Please try again."}


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 4: save_customer_name
# ═══════════════════════════════════════════════════════════════════════════
def save_customer_name(name: str, tool_context: ToolContext) -> dict[str, Any]:
    """
    Store the customer's name in session state for personalized responses.

    Args:
        name: The customer's name.

    Returns:
        Confirmation dict.
    """
    if not name or not name.strip():
        return {"error": "Please provide a valid name."}

    name = name.strip()
    tool_context.state["current_customer_name"] = name

    log.info("Customer name saved: %s", name)

    return {"status": "saved", "customer_name": name}


# ═══════════════════════════════════════════════════════════════════════════
# TOOL 5: get_session_summary
# ═══════════════════════════════════════════════════════════════════════════
def get_session_summary(tool_context: ToolContext) -> dict[str, Any]:
    """
    Return a summary of the current session context.

    Useful for showing the customer what the agent remembers.
    """
    state = tool_context.state

    return {
        "customer_name": state.get("current_customer_name"),
        "current_order_id": state.get("current_order_id"),
        "current_product_id": state.get("current_product_id"),
        "last_intent": state.get("last_intent"),
        "last_lookup_key": state.get("last_lookup_key"),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════
def _format_product(row: dict) -> dict[str, Any]:
    """Format a product row for tool response."""
    return {
        "product_id": row["product_id"],
        "name": row["name"],
        "description": row["description"],
        "category": row["category"],
        "price": float(row["price"]) if row["price"] else 0.0,
        "stock_quantity": row["stock_quantity"],
        "in_stock": (row["stock_quantity"] or 0) > 0,
        "is_active": row["is_active"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Export tool list
# ═══════════════════════════════════════════════════════════════════════════
TOOLS = [
    get_order_status,
    cancel_order,
    lookup_product,
    save_customer_name,
    get_session_summary,
]
