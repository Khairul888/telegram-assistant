"""Tool definitions for settlement and balance operations."""

SETTLEMENT_TOOLS = [
    {
        "name": "calculate_balance",
        "description": "Calculate who owes whom and settlement amounts for the trip. Use this when the user asks about balances, who owes money, or how to settle up.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_settlement_summary",
        "description": "Get a detailed summary of all settlements and transactions needed to balance the trip. Use this when the user wants a complete breakdown of payments.",
        "parameters": {
            "type": "object",
            "properties": {
                "simplified": {
                    "type": "boolean",
                    "description": "If true, return simplified settlement (minimum transactions). Default is true."
                }
            }
        }
    }
]
