"""SettlementAgent for balance calculation and settlements."""
from api.agents.base_agent import BaseAgent
from api.agents.tools.settlement_tools import SETTLEMENT_TOOLS


class SettlementAgent(BaseAgent):
    """Agent for handling settlement and balance-related requests."""

    def _define_tools(self) -> list:
        """Return settlement tool definitions."""
        return SETTLEMENT_TOOLS

    async def _call_function(self, function_name: str, args: dict,
                            user_id: str, trip_id: int) -> dict:
        """Execute settlement service calls."""
        settlement_service = self.services.get('settlement')

        if not settlement_service:
            return {"success": False, "error": "Settlement service not available"}

        if function_name == "calculate_balance":
            try:
                # Calculate running balance for the trip
                result = await settlement_service.calculate_running_balance(trip_id)
                return {"success": True, "settlements": result}
            except Exception as e:
                print(f"Error calculating balance: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "get_settlement_summary":
            try:
                simplified = args.get("simplified", True)

                # Get running balance (already simplified by default)
                settlements = await settlement_service.calculate_running_balance(trip_id)

                # Get trip expenses for additional stats
                expense_service = self.services.get('expense')
                if expense_service:
                    expenses_result = expense_service.supabase.table('expenses')\
                        .select('*')\
                        .eq('trip_id', trip_id)\
                        .execute()

                    expenses = expenses_result.data if expenses_result.data else []
                    total_expenses = sum(e.get('total_amount', 0) for e in expenses)

                    # Get unique participants from expenses
                    participants = set()
                    for expense in expenses:
                        paid_by = expense.get('paid_by')
                        if paid_by:
                            participants.add(paid_by)
                        split_amounts = expense.get('split_amounts', {})
                        participants.update(split_amounts.keys())

                    return {
                        "success": True,
                        "settlements": settlements,
                        "total_expenses": total_expenses,
                        "num_expenses": len(expenses),
                        "num_participants": len(participants),
                        "simplified": simplified
                    }
                else:
                    return {
                        "success": True,
                        "settlements": settlements,
                        "simplified": simplified
                    }

            except Exception as e:
                print(f"Error getting settlement summary: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"Unknown function: {function_name}"}

    def _format_output(self, function_name: str, output: dict) -> str:
        """Format settlement output for user."""
        if not output.get("success"):
            return f"Error: {output.get('error')}"

        if function_name == "calculate_balance":
            settlements = output.get("settlements", "")

            if "No expenses" in settlements:
                return settlements
            elif "All settled up" in settlements:
                return "All settled up! No one owes anyone."
            else:
                return f"Current Balances:\n\n{settlements}"

        elif function_name == "get_settlement_summary":
            settlements = output.get("settlements", "")
            total_expenses = output.get("total_expenses")
            num_expenses = output.get("num_expenses")
            num_participants = output.get("num_participants")

            lines = ["Settlement Summary:\n"]

            # Add trip statistics if available
            if total_expenses is not None:
                lines.append(f"Total Trip Expenses: ${total_expenses:.2f}")
                lines.append(f"Number of Expenses: {num_expenses}")
                lines.append(f"Number of Participants: {num_participants}\n")

            # Add settlements
            if "No expenses" in settlements:
                lines.append(settlements)
            elif "All settled up" in settlements:
                lines.append("All settled up! No one owes anyone.")
            else:
                lines.append("Settlements Needed:")
                lines.append(settlements)

            return "\n".join(lines)

        return "Done"
