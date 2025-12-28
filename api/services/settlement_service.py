"""Settlement calculation algorithms for expense splitting."""
from typing import Dict, List, Tuple
from collections import defaultdict


class SettlementService:
    """Calculates immediate and running balance settlements."""

    def __init__(self, expense_service):
        """Initialize with expense service dependency."""
        self.expense_service = expense_service

    def calculate_immediate_settlement(self, total_amount: float,
                                      paid_by: str,
                                      split_amounts: Dict[str, float]) -> str:
        """
        Calculate who owes whom for a single transaction.

        Args:
            total_amount: Total expense amount
            paid_by: Name of person who paid
            split_amounts: Dict mapping participant names to amounts owed

        Returns:
            str: Formatted settlement message

        Example:
            paid_by="Alice", split_amounts={"Alice": 30, "Bob": 30, "Carol": 30}
            Returns: "• Bob owes Alice $30.00\n• Carol owes Alice $30.00"
        """
        settlements = []

        for person, amount_owed in split_amounts.items():
            # Skip if person is the one who paid
            if person == paid_by:
                continue

            # Skip if amount is negligible (< 1 cent)
            if amount_owed < 0.01:
                continue

            settlements.append(f"• {person} owes {paid_by} ${amount_owed:.2f}")

        if not settlements:
            return f"No settlements needed. {paid_by} paid for themselves only."

        return "\n".join(settlements)

    async def calculate_running_balance(self, trip_id: int) -> str:
        """
        Calculate running balance across all trip expenses.
        Uses greedy algorithm to minimize number of transactions.

        Args:
            trip_id: Trip ID

        Returns:
            str: Formatted settlement message showing minimized transactions

        Algorithm:
            1. Calculate net balance for each person (total paid - total owed)
            2. Separate into creditors (positive balance) and debtors (negative)
            3. Use greedy matching to minimize transactions

        Example:
            Alice paid $90, owes $30 = +$60
            Bob paid $30, owes $30 = $0
            Carol paid $0, owes $60 = -$60
            Result: "• Carol owes Alice $60.00"
        """
        try:
            # Get all expenses for trip
            expenses = await self.expense_service.get_trip_expenses(trip_id)

            if not expenses:
                return "No expenses recorded for this trip yet."

            # Calculate net balance for each person
            balances = defaultdict(float)

            for expense in expenses:
                paid_by = expense.get('paid_by')
                split_amounts = expense.get('split_amounts')

                # Skip incomplete expenses (no split data)
                if not paid_by or not split_amounts:
                    continue

                total_paid = expense.get('total_amount', 0)

                # Person who paid gets credited the full amount
                balances[paid_by] += total_paid

                # Each person owes their share (debited)
                for person, amount in split_amounts.items():
                    balances[person] -= amount

            # Generate settlement using minimized transactions
            return self._minimize_transactions(balances)

        except Exception as e:
            print(f"Error calculating running balance: {e}")
            return f"Error calculating balance: {str(e)}"

    def _minimize_transactions(self, balances: Dict[str, float]) -> str:
        """
        Minimize number of transactions using greedy algorithm.

        Args:
            balances: Dict mapping person names to net balance

        Returns:
            str: Formatted settlement message

        Algorithm:
            - Creditors have positive balance (owed money)
            - Debtors have negative balance (owe money)
            - Match largest debtor to largest creditor iteratively
        """
        # Separate creditors (positive) and debtors (negative)
        # Ignore balances < 1 cent
        creditors = [(person, bal) for person, bal in balances.items()
                    if bal > 0.01]
        debtors = [(person, -bal) for person, bal in balances.items()
                  if bal < -0.01]

        # Check if all settled
        if not creditors and not debtors:
            return "All settled up! No one owes anyone."

        settlements = []

        # Sort debtors by amount (largest first) for greedy matching
        debtors.sort(key=lambda x: -x[1])

        # Process each debtor
        for debtor_name, debt in debtors:
            remaining_debt = debt

            # Match with creditors until debt is cleared
            for i, (creditor_name, credit) in enumerate(creditors):
                if remaining_debt <= 0.01:
                    break

                # Settle minimum of debt and credit
                settlement_amount = min(remaining_debt, credit)

                if settlement_amount > 0.01:
                    settlements.append(
                        f"• {debtor_name} owes {creditor_name} "
                        f"${settlement_amount:.2f}"
                    )

                    # Update creditor's remaining credit
                    creditors[i] = (creditor_name, credit - settlement_amount)
                    remaining_debt -= settlement_amount

        return "\n".join(settlements) if settlements else "All settled up!"

    async def get_participant_balance(self, trip_id: int, participant_name: str) -> Dict:
        """
        Get balance summary for a specific participant.

        Args:
            trip_id: Trip ID
            participant_name: Name of participant

        Returns:
            dict: {
                "total_paid": float,
                "total_owed": float,
                "net_balance": float,
                "owes_to": list of (person, amount) tuples,
                "owed_by": list of (person, amount) tuples
            }
        """
        try:
            expenses = await self.expense_service.get_trip_expenses(trip_id)

            total_paid = 0.0
            total_owed = 0.0

            for expense in expenses:
                paid_by = expense.get('paid_by')
                split_amounts = expense.get('split_amounts', {})

                # Add to total paid
                if paid_by == participant_name:
                    total_paid += expense.get('total_amount', 0)

                # Add to total owed
                if participant_name in split_amounts:
                    total_owed += split_amounts[participant_name]

            net_balance = total_paid - total_owed

            return {
                "total_paid": round(total_paid, 2),
                "total_owed": round(total_owed, 2),
                "net_balance": round(net_balance, 2),
                "status": "creditor" if net_balance > 0.01 else "debtor" if net_balance < -0.01 else "settled"
            }
        except Exception as e:
            print(f"Error getting participant balance: {e}")
            return {
                "total_paid": 0,
                "total_owed": 0,
                "net_balance": 0,
                "status": "error"
            }
