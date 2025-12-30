"""ItineraryAgent for trip schedule and activity management."""
from api.agents.base_agent import BaseAgent
from api.agents.tools.itinerary_tools import ITINERARY_TOOLS


class ItineraryAgent(BaseAgent):
    """Agent for handling itinerary and schedule-related requests."""

    def _define_tools(self) -> list:
        """Return itinerary tool definitions."""
        return ITINERARY_TOOLS

    async def _call_function(self, function_name: str, args: dict,
                            user_id: str, trip_id: int) -> dict:
        """Execute itinerary service calls."""
        itinerary_service = self.services.get('itinerary')

        if not itinerary_service:
            return {"success": False, "error": "Itinerary service not available"}

        if function_name == "get_itinerary":
            try:
                # Get filtering parameters
                day_number = args.get("day_number")
                date_filter = args.get("date")

                # Get all itinerary items
                items = await itinerary_service.get_trip_itinerary(trip_id)

                # Filter by day_number if specified
                if day_number is not None:
                    items = [item for item in items if item.get('day_order') == day_number]

                # Filter by date if specified
                if date_filter:
                    items = [item for item in items if item.get('date') == date_filter]

                return {"success": True, "items": items}
            except Exception as e:
                print(f"Error getting itinerary: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "add_itinerary_items":
            try:
                items = args.get("items", [])
                replace_existing = args.get("replace_existing", False)

                if not items:
                    return {"success": False, "error": "No items provided"}

                # If replace_existing, delete current itinerary first
                if replace_existing:
                    # Get all existing items for this trip
                    existing_items = await itinerary_service.get_trip_itinerary(trip_id)
                    # Delete each one
                    for item in existing_items:
                        await itinerary_service.delete_itinerary_item(item['id'])

                # Create new itinerary items
                result = await itinerary_service.create_itinerary_items(
                    user_id=user_id,
                    trip_id=trip_id,
                    items=items
                )

                return result
            except Exception as e:
                print(f"Error adding itinerary items: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "update_itinerary_item":
            try:
                item_id = args.get("item_id")
                if not item_id:
                    return {"success": False, "error": "item_id is required"}

                # Prepare updates dict (only include provided fields)
                updates = {}
                if "time" in args:
                    updates["time"] = args["time"]
                if "title" in args:
                    updates["title"] = args["title"]
                if "description" in args:
                    updates["description"] = args["description"]
                if "location" in args:
                    updates["location"] = args["location"]

                if not updates:
                    return {"success": False, "error": "No fields to update"}

                result = await itinerary_service.update_itinerary_item(item_id, updates)
                return result
            except Exception as e:
                print(f"Error updating itinerary item: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "delete_itinerary_item":
            try:
                item_id = args.get("item_id")
                if not item_id:
                    return {"success": False, "error": "item_id is required"}

                result = await itinerary_service.delete_itinerary_item(item_id)
                return result
            except Exception as e:
                print(f"Error deleting itinerary item: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"Unknown function: {function_name}"}

    def _format_output(self, function_name: str, output: dict) -> str:
        """Format itinerary output for user."""
        if not output.get("success"):
            return f"Error: {output.get('error')}"

        if function_name == "get_itinerary":
            items = output.get("items", [])

            if not items:
                return "No activities scheduled yet for this trip."

            # Group items by day
            by_day = {}
            for item in items:
                day = item.get('day_order') or item.get('date') or 'Unscheduled'
                if day not in by_day:
                    by_day[day] = []
                by_day[day].append(item)

            lines = []

            for day, day_items in sorted(by_day.items()):
                # Day header
                if isinstance(day, int):
                    lines.append(f"\nDay {day}:")
                elif day == 'Unscheduled':
                    lines.append(f"\nUnscheduled Activities:")
                else:
                    lines.append(f"\n{day}:")

                # Sort items by time_order, then time
                sorted_items = sorted(
                    day_items,
                    key=lambda x: (x.get('time_order', 999), x.get('time', '99:99'))
                )

                for item in sorted_items:
                    time = item.get('time', '')
                    title = item.get('title', 'Activity')
                    location = item.get('location', '')
                    description = item.get('description', '')

                    # Format: "HH:MM - Title @ Location"
                    item_line = f"  {time} - {title}" if time else f"  {title}"
                    if location:
                        item_line += f" @ {location}"
                    lines.append(item_line)

                    # Add description if present
                    if description:
                        lines.append(f"    ({description})")

            return "\n".join(lines)

        elif function_name == "add_itinerary_items":
            count = output.get("count", 0)
            items = output.get("items", [])

            if count == 0:
                return "No activities were added."
            elif count == 1:
                return "Added 1 activity to your itinerary!"
            else:
                return f"Added {count} activities to your itinerary!"

        elif function_name == "update_itinerary_item":
            item = output.get("item", {})
            title = item.get('title', 'Activity')
            return f"Updated '{title}' successfully!"

        elif function_name == "delete_itinerary_item":
            return "Activity removed from itinerary."

        return "Done"
