"""Tool definitions for expense-related operations."""

EXPENSE_TOOLS = [
    {
        "name": "create_expense",
        "description": "Create a new expense entry for the current trip. Use this when the user mentions spending money, paying for something, or wants to track an expense.",
        "parameters": {
            "type": "object",
            "properties": {
                "merchant_name": {
                    "type": "string",
                    "description": "Name of the merchant, restaurant, or place where money was spent. Use 'Expense' as default if not specified."
                },
                "total_amount": {
                    "type": "number",
                    "description": "Total expense amount in dollars (numeric value without currency symbol)"
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "accommodation", "entertainment", "shopping", "other"],
                    "description": "Category of the expense. Use 'other' if not specified."
                },
                "paid_by": {
                    "type": "string",
                    "description": "Name of the person who paid for this expense"
                },
                "split_between": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of people to split this expense between (including the payer). If user says 'everyone' or 'all', include all trip participants."
                }
            },
            "required": ["total_amount", "paid_by"]
        }
    },
    {
        "name": "list_expenses",
        "description": "Get all expenses for the current trip. Use this when the user asks to see expenses, view spending, or check what they've spent.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "accommodation", "entertainment", "shopping", "other"],
                    "description": "Optional: Filter expenses by category"
                }
            }
        }
    },
    {
        "name": "get_expense_summary",
        "description": "Get expense statistics and summary for the current trip. Use this when the user asks about total spending, spending by category, or wants an overview.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "delete_expense",
        "description": "Delete an expense from the current trip. Use this when the user wants to remove or delete an expense.",
        "parameters": {
            "type": "object",
            "properties": {
                "expense_id": {
                    "type": "integer",
                    "description": "ID of the expense to delete (get this from list_expenses first)"
                }
            },
            "required": ["expense_id"]
        }
    },
    {
        "name": "update_expense",
        "description": "Update an existing expense. Use this when the user wants to modify an expense amount, description, or other details.",
        "parameters": {
            "type": "object",
            "properties": {
                "expense_id": {
                    "type": "integer",
                    "description": "ID of the expense to update (get this from list_expenses first)"
                },
                "merchant_name": {
                    "type": "string",
                    "description": "New merchant name (optional)"
                },
                "total_amount": {
                    "type": "number",
                    "description": "New total amount (optional)"
                },
                "category": {
                    "type": "string",
                    "enum": ["food", "transport", "accommodation", "entertainment", "shopping", "other"],
                    "description": "New category (optional)"
                }
            },
            "required": ["expense_id"]
        }
    }
]
