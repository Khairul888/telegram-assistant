"""Itinerary management service for trip schedule tracking."""
from typing import Dict, List, Optional
from datetime import datetime, date


class ItineraryService:
    """Manages trip itinerary creation, retrieval, and updates."""

    def __init__(self, supabase_client):
        """Initialize with Supabase client."""
        self.supabase = supabase_client

    async def create_itinerary_items(self, user_id: str, trip_id: int,
                                     items: List[Dict]) -> Dict:
        """
        Create multiple itinerary items from extracted data.

        Args:
            user_id: Telegram user ID
            trip_id: Trip ID to associate items with
            items: List of dicts with keys: date, time, title, description,
                   location, category, day_order, time_order, etc.

        Returns:
            dict: {"success": bool, "count": int, "items": list} or error
        """
        try:
            # Prepare items for insertion
            itinerary_items = []
            for item in items:
                item_data = {
                    "user_id": user_id,
                    "trip_id": trip_id,
                    "date": item.get("date"),
                    "time": item.get("time"),
                    "title": item["title"],
                    "description": item.get("description"),
                    "location": item.get("location"),
                    "category": item.get("category", "activity"),
                    "duration_minutes": item.get("duration_minutes"),
                    "confirmation_number": item.get("confirmation_number"),
                    "cost": item.get("cost"),
                    "currency": item.get("currency", "USD"),
                    "notes": item.get("notes"),
                    "source": item.get("source", "detected"),
                    "raw_extracted_data": item.get("raw_extracted_data", item),
                    "day_order": item.get("day_order"),
                    "time_order": item.get("time_order")
                }
                itinerary_items.append(item_data)

            # Bulk insert
            result = self.supabase.table('trip_itinerary').insert(itinerary_items).execute()

            if not result.data:
                return {"success": False, "error": "Failed to create itinerary items"}

            return {
                "success": True,
                "count": len(result.data),
                "items": result.data
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_trip_itinerary(self, trip_id: int, start_date: str = None,
                                 end_date: str = None) -> List[Dict]:
        """
        Get all itinerary items for a trip, optionally filtered by date range.

        Args:
            trip_id: Trip ID
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)

        Returns:
            list: List of itinerary item dictionaries, ordered by date and time
        """
        try:
            query = self.supabase.table('trip_itinerary')\
                .select('*')\
                .eq('trip_id', trip_id)

            if start_date:
                query = query.gte('date', start_date)
            if end_date:
                query = query.lte('date', end_date)

            result = query.order('date')\
                .order('time_order')\
                .order('time')\
                .execute()

            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting trip itinerary: {e}")
            return []

    async def update_itinerary_item(self, item_id: int, updates: Dict) -> Dict:
        """
        Update an itinerary item.

        Args:
            item_id: Itinerary item ID
            updates: Dict with fields to update

        Returns:
            dict: {"success": bool, "item": dict} or error
        """
        try:
            # Only allow certain fields to be updated
            allowed_fields = [
                'date', 'time', 'title', 'description', 'location', 'category',
                'duration_minutes', 'confirmation_number', 'cost', 'currency',
                'notes', 'day_order', 'time_order'
            ]
            update_data = {k: v for k, v in updates.items() if k in allowed_fields}

            result = self.supabase.table('trip_itinerary')\
                .update(update_data)\
                .eq('id', item_id)\
                .execute()

            if not result.data:
                return {"success": False, "error": "Failed to update itinerary item"}

            return {"success": True, "item": result.data[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def delete_itinerary_item(self, item_id: int) -> Dict:
        """
        Delete an itinerary item.

        Args:
            item_id: Itinerary item ID

        Returns:
            dict: {"success": bool} or error
        """
        try:
            result = self.supabase.table('trip_itinerary')\
                .delete()\
                .eq('id', item_id)\
                .execute()

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_itinerary_summary(self, trip_id: int) -> Dict:
        """
        Get summary statistics for trip itinerary.

        Args:
            trip_id: Trip ID

        Returns:
            dict: {
                "total_items": int,
                "by_category": dict,
                "by_day": dict,
                "date_range": {"start": str, "end": str}
            }
        """
        try:
            items = await self.get_trip_itinerary(trip_id)

            if not items:
                return {
                    "total_items": 0,
                    "by_category": {},
                    "by_day": {},
                    "date_range": None
                }

            # Group by category
            by_category = {}
            for item in items:
                category = item.get('category', 'other')
                by_category[category] = by_category.get(category, 0) + 1

            # Group by day
            by_day = {}
            for item in items:
                day = item.get('date')
                if day:
                    by_day[day] = by_day.get(day, 0) + 1

            # Get date range
            dates = [item['date'] for item in items if item.get('date')]
            date_range = None
            if dates:
                date_range = {
                    "start": min(dates),
                    "end": max(dates)
                }

            return {
                "total_items": len(items),
                "by_category": by_category,
                "by_day": by_day,
                "date_range": date_range
            }
        except Exception as e:
            print(f"Error getting itinerary summary: {e}")
            return {"total_items": 0, "by_category": {}, "by_day": {}, "date_range": None}
