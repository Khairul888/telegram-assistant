"""Expense tracking and splitting service."""
from typing import Dict, List, Optional
from datetime import datetime


class ExpenseService:
    """Manages expense creation, retrieval, and splitting."""

    def __init__(self, supabase_client):
        """Initialize with Supabase client."""
        self.supabase = supabase_client

    async def create_expense(self, user_id: str, trip_id: int,
                            merchant_name: str, total_amount: float,
                            paid_by: str = None, split_between: List[str] = None,
                            transaction_date: str = None, category: str = "other") -> Dict:
        """
        Create a general expense record (for manual entry).

        Args:
            user_id: Telegram user ID
            trip_id: Trip ID to associate expense with
            merchant_name: Description of the expense
            total_amount: Total expense amount
            paid_by: Name of person who paid (optional)
            split_between: List of participant names (optional)
            transaction_date: Date in YYYY-MM-DD format (optional)
            category: Expense category (optional)

        Returns:
            dict: {"success": bool, "expense_id": int, "expense": dict} or error
        """
        try:
            expense_data = {
                "user_id": user_id,
                "trip_id": trip_id,
                "merchant_name": merchant_name,
                "total_amount": float(total_amount),
                "category": category,
                "transaction_date": transaction_date,
                "currency": "USD",
                "paid_by": paid_by,
                "split_between": split_between
            }

            result = self.supabase.table('expenses').insert(expense_data).execute()

            if not result.data:
                return {"success": False, "error": "Failed to create expense"}

            expense_id = result.data[0]['id']

            return {
                "success": True,
                "expense_id": expense_id,
                "expense": result.data[0]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def create_expense_from_receipt(self, user_id: str, trip_id: int,
                                         receipt_data: Dict) -> Dict:
        """
        Create expense record from OCR-extracted receipt data.
        Split fields (paid_by, split_between, split_amounts) are left NULL
        until user selects split type.

        Args:
            user_id: Telegram user ID
            trip_id: Trip ID to associate expense with
            receipt_data: Dict with keys: merchant_name, total, date, items, etc.

        Returns:
            dict: {"success": bool, "expense_id": int, "expense": dict} or error
        """
        try:
            expense_data = {
                "user_id": user_id,
                "trip_id": trip_id,
                "merchant_name": receipt_data.get("merchant_name"),
                "location": receipt_data.get("location"),
                "transaction_date": receipt_data.get("date"),
                "transaction_time": receipt_data.get("time"),
                "category": receipt_data.get("category", "other"),
                "subtotal": float(receipt_data.get("subtotal", 0)) if receipt_data.get("subtotal") else None,
                "tax_amount": float(receipt_data.get("tax", 0)) if receipt_data.get("tax") else None,
                "tip_amount": float(receipt_data.get("tip", 0)) if receipt_data.get("tip") else None,
                "total_amount": float(receipt_data.get("total", 0)),
                "currency": receipt_data.get("currency", "USD"),
                "items": receipt_data.get("items", []),
                "payment_method": receipt_data.get("payment_method"),
                "confidence_score": 0.85,
                "raw_extracted_data": receipt_data,
                # Split fields will be populated after user selection
                "paid_by": None,
                "split_between": None,
                "split_amounts": None
            }

            result = self.supabase.table('expenses').insert(expense_data).execute()

            if not result.data:
                return {"success": False, "error": "Failed to create expense"}

            expense_id = result.data[0]['id']

            return {
                "success": True,
                "expense_id": expense_id,
                "expense": result.data[0]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def update_expense_split(self, expense_id: int, paid_by: str,
                                  split_type: str, participants: List[str],
                                  total_amount: float) -> Dict:
        """
        Update expense with split information after user selection.

        Args:
            expense_id: Expense ID to update
            paid_by: Name of person who paid
            split_type: 'even' or 'custom'
            participants: List of participant names
            total_amount: Total expense amount

        Returns:
            dict: {"success": bool, "expense": dict} or error
        """
        try:
            if split_type == "even":
                # Split evenly among all participants
                per_person = total_amount / len(participants)
                split_amounts = {
                    participant: round(per_person, 2)
                    for participant in participants
                }
            elif split_type == "custom":
                # Custom split (future iteration)
                return {
                    "success": False,
                    "error": "Custom split not yet implemented. Please use 'even' split."
                }
            else:
                return {"success": False, "error": f"Invalid split_type: {split_type}"}

            update_data = {
                "paid_by": paid_by,
                "split_between": participants,  # PostgreSQL array
                "split_amounts": split_amounts  # JSONB
            }

            result = self.supabase.table('expenses')\
                .update(update_data)\
                .eq('id', expense_id)\
                .execute()

            if not result.data:
                return {"success": False, "error": "Failed to update expense"}

            return {"success": True, "expense": result.data[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_trip_expenses(self, trip_id: int) -> List[Dict]:
        """
        Get all expenses for a trip, ordered by date (newest first).

        Args:
            trip_id: Trip ID

        Returns:
            list: List of expense dictionaries
        """
        try:
            result = self.supabase.table('expenses')\
                .select('*')\
                .eq('trip_id', trip_id)\
                .order('transaction_date', desc=True)\
                .execute()

            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting trip expenses: {e}")
            return []

    async def get_expense_by_id(self, expense_id: int) -> Optional[Dict]:
        """
        Get expense by ID.

        Args:
            expense_id: Expense ID

        Returns:
            dict: Expense data or None
        """
        try:
            result = self.supabase.table('expenses')\
                .select('*')\
                .eq('id', expense_id)\
                .execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error getting expense: {e}")
            return None

    async def get_trip_expenses_summary(self, trip_id: int) -> Dict:
        """
        Get summary statistics for trip expenses.

        Args:
            trip_id: Trip ID

        Returns:
            dict: {
                "total_spent": float,
                "expense_count": int,
                "by_category": dict,
                "by_participant": dict
            }
        """
        try:
            expenses = await self.get_trip_expenses(trip_id)

            if not expenses:
                return {
                    "total_spent": 0,
                    "expense_count": 0,
                    "by_category": {},
                    "by_participant": {}
                }

            total_spent = sum(e.get('total_amount', 0) for e in expenses)
            expense_count = len(expenses)

            # Group by category
            by_category = {}
            for expense in expenses:
                category = expense.get('category', 'other')
                amount = expense.get('total_amount', 0)
                by_category[category] = by_category.get(category, 0) + amount

            # Group by who paid
            by_participant = {}
            for expense in expenses:
                paid_by = expense.get('paid_by')
                if paid_by:
                    amount = expense.get('total_amount', 0)
                    by_participant[paid_by] = by_participant.get(paid_by, 0) + amount

            return {
                "total_spent": round(total_spent, 2),
                "expense_count": expense_count,
                "by_category": {k: round(v, 2) for k, v in by_category.items()},
                "by_participant": {k: round(v, 2) for k, v in by_participant.items()}
            }
        except Exception as e:
            print(f"Error getting expense summary: {e}")
            return {"total_spent": 0, "expense_count": 0, "by_category": {}, "by_participant": {}}
