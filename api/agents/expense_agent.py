"""ExpenseAgent for expense tracking and splitting."""
from api.agents.base_agent import BaseAgent
from api.agents.tools.expense_tools import EXPENSE_TOOLS


class ExpenseAgent(BaseAgent):
    """Agent for handling expense-related requests."""

    def _define_tools(self) -> list:
        """Return expense tool definitions."""
        return EXPENSE_TOOLS

    async def _call_function(self, function_name: str, args: dict,
                            user_id: str, trip_id: int) -> dict:
        """Execute expense service calls."""
        expense_service = self.services.get('expense')
        settlement_service = self.services.get('settlement')

        if not expense_service:
            return {"success": False, "error": "Expense service not available"}

        if function_name == "create_expense":
            try:
                result = await expense_service.create_expense(
                    user_id=user_id,
                    trip_id=trip_id,
                    merchant_name=args.get("merchant_name", "Expense"),
                    total_amount=float(args.get("total_amount")),
                    category=args.get("category", "other"),
                    paid_by=args.get("paid_by"),
                    split_between=args.get("split_between")
                )
                return result
            except Exception as e:
                print(f"Error creating expense: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "list_expenses":
            try:
                # Get trip expenses
                expenses_result = expense_service.supabase.table('expenses')\
                    .select('*')\
                    .eq('trip_id', trip_id)\
                    .order('transaction_date', desc=True)\
                    .execute()

                expenses = expenses_result.data if expenses_result.data else []

                # Filter by category if specified
                category = args.get("category")
                if category:
                    expenses = [e for e in expenses if e.get('category') == category]

                return {"success": True, "expenses": expenses}
            except Exception as e:
                return {"success": False, "error": str(e)}

        elif function_name == "get_expense_summary":
            try:
                # Get all expenses
                expenses_result = expense_service.supabase.table('expenses')\
                    .select('*')\
                    .eq('trip_id', trip_id)\
                    .execute()

                expenses = expenses_result.data if expenses_result.data else []

                # Calculate summary
                total = sum(e.get('total_amount', 0) for e in expenses)

                # Group by category
                by_category = {}
                for expense in expenses:
                    category = expense.get('category', 'other')
                    amount = expense.get('total_amount', 0)
                    by_category[category] = by_category.get(category, 0) + amount

                # Group by payer
                by_payer = {}
                for expense in expenses:
                    payer = expense.get('paid_by', 'Unknown')
                    amount = expense.get('total_amount', 0)
                    by_payer[payer] = by_payer.get(payer, 0) + amount

                return {
                    "success": True,
                    "total": total,
                    "by_category": by_category,
                    "by_payer": by_payer,
                    "count": len(expenses)
                }
            except Exception as e:
                return {"success": False, "error": str(e)}

        elif function_name == "delete_expense":
            try:
                expense_id = args.get("expense_id")
                expense_service.supabase.table('expenses')\
                    .delete()\
                    .eq('id', expense_id)\
                    .execute()
                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        elif function_name == "update_expense":
            try:
                expense_id = args.get("expense_id")
                update_data = {}

                if "merchant_name" in args:
                    update_data["merchant_name"] = args["merchant_name"]
                if "total_amount" in args:
                    update_data["total_amount"] = float(args["total_amount"])
                if "category" in args:
                    update_data["category"] = args["category"]

                if not update_data:
                    return {"success": False, "error": "No fields to update"}

                expense_service.supabase.table('expenses')\
                    .update(update_data)\
                    .eq('id', expense_id)\
                    .execute()

                return {"success": True}
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"Unknown function: {function_name}"}

    def _format_output(self, function_name: str, output: dict) -> str:
        """Format expense output for user."""
        if not output.get("success"):
            return f"Error: {output.get('error')}"

        if function_name == "create_expense":
            expense = output.get("expense", {})
            merchant = expense.get('merchant_name', 'Unknown')
            amount = expense.get('total_amount', 0)
            date = expense.get('transaction_date', 'Unknown date')
            paid_by = expense.get('paid_by', 'Unknown')
            split_between = expense.get('split_between', [])

            response = f"""Expense added!

💰 {merchant} - ${amount:.2f}
📅 {date}
👤 Paid by: {paid_by}"""

            if split_between:
                response += f"\n👥 Split with: {', '.join(split_between)}"

            return response

        elif function_name == "list_expenses":
            expenses = output.get("expenses", [])
            if not expenses:
                return "No expenses yet for this trip."

            total = sum(e.get('total_amount', 0) for e in expenses)
            lines = [f"Trip Expenses (Total: ${total:.2f}):\n"]

            for exp in expenses[:10]:  # Limit to 10
                merchant = exp.get('merchant_name', 'Unknown')
                amount = exp.get('total_amount', 0)
                category = exp.get('category', 'other')
                paid_by = exp.get('paid_by', 'Unknown')
                date = exp.get('transaction_date', '')

                # Build the main expense line
                expense_line = f"• {merchant} - ${amount:.2f} ({category})"
                if date:
                    expense_line += f" - {date}"
                lines.append(expense_line)

                # Add payer info
                lines.append(f"  Paid by: {paid_by}")

                # Add per-person breakdown if available
                split_amounts = exp.get('split_amounts')
                if split_amounts and isinstance(split_amounts, dict):
                    lines.append("  Owed by:")
                    for person, person_amount in split_amounts.items():
                        lines.append(f"    - {person}: ${person_amount:.2f}")
                elif exp.get('split_between'):
                    # Fallback: calculate equal split if split_amounts not available
                    split_between = exp.get('split_between', [])
                    if split_between:
                        per_person = amount / len(split_between)
                        lines.append("  Split equally among:")
                        for person in split_between:
                            lines.append(f"    - {person}: ${per_person:.2f}")

                lines.append("")  # Add blank line between expenses

            if len(expenses) > 10:
                lines.append(f"...and {len(expenses) - 10} more expenses")

            return "\n".join(lines)

        elif function_name == "get_expense_summary":
            total = output.get("total", 0)
            by_category = output.get("by_category", {})
            by_payer = output.get("by_payer", {})
            count = output.get("count", 0)

            lines = [f"Expense Summary:\n"]
            lines.append(f"Total Spent: ${total:.2f}")
            lines.append(f"Number of Expenses: {count}\n")

            if by_category:
                lines.append("By Category:")
                for category, amount in sorted(by_category.items(), key=lambda x: -x[1]):
                    lines.append(f"  • {category.title()}: ${amount:.2f}")

            if by_payer:
                lines.append("\nBy Payer:")
                for payer, amount in sorted(by_payer.items(), key=lambda x: -x[1]):
                    lines.append(f"  • {payer}: ${amount:.2f}")

            return "\n".join(lines)

        elif function_name == "delete_expense":
            return "Expense deleted successfully"

        elif function_name == "update_expense":
            return "Expense updated successfully"

        return "Done"
