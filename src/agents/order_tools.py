import re
from typing import Dict, Any
from google.adk.tools import ToolContext

MOCK_ORDERS = {
    "ORD-001": {
        "order_id": "ORD-001",
        "status": "Shipped",
        "eta": "5 Jun 2026",
        "carrier": "BlueDart",
    },
    "ORD-002": {
        "order_id": "ORD-002",
        "status": "Processing",
        "eta": "7 Jun 2026",
        "carrier": "DTDC",
    },
    "ORD-003": {
        "order_id": "ORD-003",
        "status": "Delivered",
        "eta": "Already delivered",
        "carrier": "FedEx",
    },
}


def _is_valid_order_id(order_id: str) -> bool:
    """
    Basic validation for order ID format: ORD-XXX
    """
    if not isinstance(order_id, str):
        return False
    return bool(re.match(r"^ORD-\d{3}$", order_id.strip()))

def store_customer_name(customer_name: str, tool_context: ToolContext) -> Dict[str, str]:
    """
    Store the customer's name in the session state.
    
    Args:
        customer_name: The customer's name
        tool_context: Tool execution context
        
    Returns:
        dict: Confirmation message
    """
    tool_context.state["customer_name"] = customer_name.strip()
    return {"message": f"Stored customer name: {customer_name}"}


def get_order_status(order_id: str,tool_context: ToolContext) -> Dict[str, Any]:
    """
    Fetch order status from mock data.
    Fetch order status and store last order ID in session state.

    Returns:
        dict: order details or error message
    """

    if not _is_valid_order_id(order_id):
        return {"error": "Invalid order ID format."}

    order_id = order_id.strip()

    order_data = MOCK_ORDERS.get(order_id)

    if not order_data:
        return {"error": f"Order {order_id} not found."}
    
    tool_context.state["last_order_id"] = order_id

    return {
        "order_id": order_data["order_id"],
        "status": order_data["status"],
        "eta": order_data["eta"],
        "carrier": order_data["carrier"],
    }
