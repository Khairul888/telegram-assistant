"""ItineraryAgent for trip schedule and activity management."""
from api.agents.base_agent import BaseAgent
from api.agents.tools.itinerary_tools import ITINERARY_TOOLS


class ItineraryAgent(BaseAgent):
    """Agent for handling itinerary and schedule-related requests."""

    def _define_tools(self) -> list:
        """Return itinerary tool definitions."""
        return ITINERARY_TOOLS

    async def _call_function(self, function_name: str, args: dict,
                            user_id: str, chat_id: str, trip_id: int) -> dict:
        """Execute itinerary service calls."""
        itinerary_service = self.services.get('itinerary')
        trip_service = self.services.get('trip')

        if not itinerary_service:
            return {"success": False, "error": "Itinerary service not available"}

        if function_name == "parse_itinerary_text":
            try:
                text = args.get("text", "")
                if not text:
                    return {"success": False, "error": "No text provided"}

                # Get trip start date for relative date calculation
                trip = await trip_service.get_trip_by_id(trip_id)
                trip_start_date = trip.get('start_date') if trip else None

                # Extract itinerary using Gemini
                extraction_result = await self.gemini.extract_itinerary_from_text(
                    text, trip_start_date
                )

                if not extraction_result.get("success"):
                    return {"success": False, "error": "Could not extract itinerary from text"}

                items = extraction_result.get("items", [])
                summary = extraction_result.get("summary", "")

                if not items:
                    return {"success": False, "error": "No itinerary items found in text"}

                # Format preview message (used in multiple flows below)
                preview_lines = []
                for i, item in enumerate(items[:5]):  # Show first 5 as preview
                    time_str = f"{item.get('time', '')} " if item.get('time') else ""
                    title = item.get('title', 'Activity')
                    day = item.get('day_order', '?')
                    preview_lines.append(f"  Day {day}: {time_str}{title}")

                preview = "\n".join(preview_lines)
                if len(items) > 5:
                    preview += f"\n  ... and {len(items) - 5} more activities"

                # Check if trip has start_date
                trip = await trip_service.get_trip_by_id(trip_id)
                has_start_date = trip.get('start_date') if trip else False

                # Check if items have dates or if we need to ask for start date
                items_have_dates = any(item.get('date') for item in items)
                items_have_day_order = any(item.get('day_order') for item in items)

                # If items only have day_order and trip has no start_date, ask user
                if items_have_day_order and not items_have_dates and not has_start_date:
                    # Store in session for date collection
                    await trip_service.get_or_update_session(
                        user_id,
                        chat_id,
                        state='awaiting_trip_start_date',
                        context={
                            'itinerary_items': items,
                            'itinerary_summary': summary,
                            'trip_id': trip_id
                        }
                    )

                    message = f"""I found {len(items)} activities organized by day number.

{preview}

To save these with the correct dates, what date does **Day 1** start?

Please respond with a date (e.g., "January 15" or "2026-01-15")"""

                    await self.telegram.send_message(chat_id, message)

                    return {
                        "success": True,
                        "already_sent": True,
                        "count": len(items),
                        "items": items,
                        "summary": summary
                    }

                # Store in session for confirmation
                await trip_service.get_or_update_session(
                    user_id,
                    chat_id,
                    state='awaiting_itinerary_confirmation',
                    context={
                        'itinerary_items': items,
                        'itinerary_summary': summary,
                        'trip_id': trip_id
                    }
                )

                message = f"""I found {len(items)} activities in your itinerary:

{preview}

Would you like me to save this to your trip schedule?"""

                # Create inline keyboard for confirmation
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "✅ Yes, save it", "callback_data": "itinerary_confirm:yes"},
                            {"text": "❌ No, cancel", "callback_data": "itinerary_confirm:no"}
                        ]
                    ]
                }

                # Send message with keyboard directly
                await self.telegram.send_message_with_keyboard(chat_id, message, keyboard)

                return {
                    "success": True,
                    "already_sent": True,  # Flag that we already sent the message
                    "count": len(items),
                    "items": items,
                    "summary": summary
                }
            except Exception as e:
                print(f"Error parsing itinerary text: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "save_pending_itinerary":
            try:
                # Get session context
                session = await trip_service.get_or_update_session(user_id, chat_id)
                context = session.get('conversation_context', {})

                items = context.get('itinerary_items', [])
                session_trip_id = context.get('trip_id')

                if not items or not session_trip_id:
                    return {"success": False, "error": "No pending itinerary found. Please paste an itinerary first."}

                # Verify trip_id matches
                if session_trip_id != trip_id:
                    return {"success": False, "error": "Trip mismatch. Please try again."}

                # Create itinerary items
                result = await itinerary_service.create_itinerary_items(
                    user_id=user_id,
                    trip_id=trip_id,
                    items=items
                )

                # Clear session state
                await trip_service.clear_conversation_state(user_id, chat_id)

                return result
            except Exception as e:
                print(f"Error saving pending itinerary: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "get_itinerary":
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

        if function_name == "parse_itinerary_text":
            count = output.get("count", 0)
            items = output.get("items", [])

            if count == 0:
                return "I couldn't find any activities in that text. Please try again."

            # Show brief summary of found items
            preview_lines = []
            for i, item in enumerate(items[:5]):  # Show first 5 as preview
                time_str = f"{item.get('time', '')} " if item.get('time') else ""
                title = item.get('title', 'Activity')
                day = item.get('day_order', '?')
                preview_lines.append(f"  Day {day}: {time_str}{title}")

            preview = "\n".join(preview_lines)
            if count > 5:
                preview += f"\n  ... and {count - 5} more activities"

            return f"""I found {count} activities in your itinerary:

{preview}

Would you like me to save this to your trip schedule?"""

        elif function_name == "save_pending_itinerary":
            count = output.get("count", 0)
            if count == 0:
                return "No activities were saved."
            elif count == 1:
                return "Saved 1 activity to your itinerary!"
            else:
                return f"Saved {count} activities to your itinerary!"

        elif function_name == "get_itinerary":
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
