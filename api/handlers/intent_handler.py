"""Intent detection handler for conversational itinerary and places."""
from typing import Dict


class IntentHandler:
    """Handles conversational detection of itineraries and places."""

    def __init__(self, gemini_service, itinerary_service, places_service,
                 trip_service, telegram_utils):
        """
        Initialize with service dependencies.

        Args:
            gemini_service: GeminiService instance
            itinerary_service: ItineraryService instance
            places_service: PlacesService instance
            trip_service: TripService instance
            telegram_utils: TelegramUtils instance
        """
        self.gemini = gemini_service
        self.itinerary = itinerary_service
        self.places = places_service
        self.trips = trip_service
        self.telegram = telegram_utils

    async def handle_itinerary_detection(self, user_id: str, chat_id: str,
                                        text: str, trip: dict) -> Dict:
        """
        Handle itinerary paste detection flow.

        Flow:
        1. Extract structured data from text via Gemini
        2. Generate human-readable summary
        3. Store in session context
        4. Ask user for confirmation with inline keyboard

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            text: User's pasted itinerary text
            trip: Current trip dict

        Returns:
            dict: {"handled": bool, "response": str or None}
        """
        try:
            # Extract itinerary data
            trip_start_date = trip.get('start_date')
            extraction_result = await self.gemini.extract_itinerary_from_text(
                text, trip_start_date
            )

            if not extraction_result.get("success"):
                return {"handled": False, "response": None}

            items = extraction_result.get("items", [])
            summary = extraction_result.get("summary", "")

            if not items:
                return {"handled": False, "response": None}

            # Store in session for confirmation
            await self.trips.get_or_update_session(
                user_id,
                state='awaiting_itinerary_confirmation',
                context={
                    'itinerary_items': items,
                    'itinerary_summary': summary,
                    'trip_id': trip['id']
                }
            )

            # Format summary for display
            formatted_summary = self._format_itinerary_summary(items)

            # Create confirmation keyboard
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "✅ Yes, save it", "callback_data": "itinerary_confirm:yes"},
                        {"text": "❌ No, cancel", "callback_data": "itinerary_confirm:no"}
                    ]
                ]
            }

            message = f"""📅 I detected an itinerary! Here's what I found:

{formatted_summary}

Would you like me to save this to your trip schedule?"""

            # Send message with keyboard
            await self.telegram.send_message_with_keyboard(chat_id, message, keyboard)

            return {"handled": True, "response": None}  # Already sent

        except Exception as e:
            print(f"Error handling itinerary detection: {e}")
            return {"handled": False, "response": None}

    async def handle_itinerary_confirmation(self, user_id: str, chat_id: str,
                                           confirmed: bool) -> str:
        """
        Handle itinerary confirmation callback.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            confirmed: Whether user confirmed

        Returns:
            str: Response message
        """
        try:
            # Get session context
            session = await self.trips.get_or_update_session(user_id, chat_id)
            context = session.get('conversation_context', {})

            items = context.get('itinerary_items', [])
            trip_id = context.get('trip_id')

            if not confirmed:
                # Clear session
                await self.trips.clear_conversation_state(user_id, chat_id)
                return "Itinerary cancelled. No changes made."

            if not items or not trip_id:
                await self.trips.clear_conversation_state(user_id, chat_id)
                return "Error: Itinerary data not found. Please try again."

            # Save itinerary items
            result = await self.itinerary.create_itinerary_items(
                user_id, trip_id, items
            )

            # Clear session
            await self.trips.clear_conversation_state(user_id, chat_id)

            if result.get("success"):
                count = result.get("count", 0)
                return f"""✅ Itinerary saved!

Added {count} activities to your trip schedule.
View anytime with /itinerary"""
            else:
                return f"❌ Error saving itinerary: {result.get('error')}"

        except Exception as e:
            await self.trips.clear_conversation_state(user_id, chat_id)
            return f"❌ Error: {str(e)}"

    async def handle_place_detection(self, user_id: str, chat_id: str,
                                    text: str, trip: dict) -> Dict:
        """
        Handle place mention detection flow.

        Flow:
        1. Extract place name via Gemini
        2. Ask user to select category
        3. Store in session for confirmation

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            text: User message mentioning a place
            trip: Current trip dict

        Returns:
            dict: {"handled": bool, "response": str or None}
        """
        try:
            # Extract place info
            extraction_result = await self.gemini.extract_place_from_text(text)

            if not extraction_result.get("success"):
                return {"handled": False, "response": None}

            place_name = extraction_result.get("name")
            suggested_category = extraction_result.get("suggested_category", "other")
            notes = extraction_result.get("notes", "")

            if not place_name:
                return {"handled": False, "response": None}

            # Store in session
            await self.trips.get_or_update_session(
                user_id,
                state='awaiting_place_category',
                context={
                    'place_name': place_name,
                    'place_notes': notes,
                    'suggested_category': suggested_category,
                    'trip_id': trip['id']
                }
            )

            # Create category selection keyboard
            categories = [
                ("🍽️ Restaurant", "restaurant"),
                ("🏛️ Attraction", "attraction"),
                ("🛍️ Shopping", "shopping"),
                ("🍻 Nightlife", "nightlife"),
                ("📍 Other", "other")
            ]

            # Reorder to put suggested category first
            sorted_categories = sorted(
                categories,
                key=lambda x: 0 if x[1] == suggested_category else 1
            )

            keyboard = {
                "inline_keyboard": [
                    [{"text": label, "callback_data": f"place_category:{category}"}]
                    for label, category in sorted_categories
                ]
            }

            message = f"""📍 I see you want to check out: {place_name}

What type of place is this?"""

            # Send message with keyboard
            await self.telegram.send_message_with_keyboard(chat_id, message, keyboard)

            return {"handled": True, "response": None}  # Already sent

        except Exception as e:
            print(f"Error handling place detection: {e}")
            return {"handled": False, "response": None}

    async def handle_place_category_selection(self, user_id: str, chat_id: str,
                                              category: str) -> str:
        """
        Handle place category selection callback.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            category: Selected category

        Returns:
            str: Response message
        """
        try:
            # Get session context
            session = await self.trips.get_or_update_session(user_id, chat_id)
            context = session.get('conversation_context', {})

            place_name = context.get('place_name')
            notes = context.get('place_notes', '')
            trip_id = context.get('trip_id')

            if not place_name or not trip_id:
                await self.trips.clear_conversation_state(user_id, chat_id)
                return "Error: Place data not found. Please try again."

            # Save place to wishlist
            result = await self.places.add_place(
                user_id, trip_id, place_name, category, notes=notes
            )

            # Clear session
            await self.trips.clear_conversation_state(user_id, chat_id)

            if result.get("success"):
                category_emoji = {
                    "restaurant": "🍽️",
                    "attraction": "🏛️",
                    "shopping": "🛍️",
                    "nightlife": "🍻",
                    "other": "📍"
                }.get(category, "📍")

                return f"""✅ Added to your wishlist!

{category_emoji} {place_name}
Category: {category.title()}

View your full wishlist with /wishlist"""
            else:
                return f"❌ Error saving place: {result.get('error')}"

        except Exception as e:
            await self.trips.clear_conversation_state(user_id, chat_id)
            return f"❌ Error: {str(e)}"

    async def handle_google_maps_url(self, user_id: str, chat_id: str,
                                     url: str, trip: dict) -> Dict:
        """
        Handle Google Maps URL detection and auto-save.

        Flow:
        1. Extract Place ID from URL
        2. Fetch details from Google Places API
        3. Auto-save with rich metadata

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            url: Google Maps URL
            trip: Current trip dict

        Returns:
            dict: {"handled": bool, "response": str}
        """
        try:
            # Extract Place ID from URL
            place_id = await self.places.extract_place_id_from_url(url)

            if not place_id:
                return {
                    "handled": True,
                    "response": "I see a Google Maps link, but couldn't extract place details. You can still add it manually!"
                }

            # Fetch place details
            details = await self.places._fetch_place_details(place_id)

            if not details:
                return {
                    "handled": True,
                    "response": "I found the place ID, but couldn't fetch details from Google Places API. Check your GOOGLE_MAPS_API_KEY."
                }

            # Determine category based on place types
            place_name = details.get("name", "Unknown Place")

            # Auto-categorize (simple heuristic - could be improved)
            category = "attraction"  # Default

            # Save to wishlist with rich data
            result = await self.places.add_place(
                user_id=user_id,
                trip_id=trip['id'],
                name=place_name,
                category=category,
                google_place_id=place_id,
                google_maps_url=url
            )

            if result.get("success"):
                place_data = result.get("place", {})
                rating = place_data.get("rating")
                address = place_data.get("address", "")

                rating_text = f" ⭐ {rating}" if rating else ""
                address_text = f"\n📍 {address}" if address else ""

                return {
                    "handled": True,
                    "response": f"""✅ Added from Google Maps!

{place_name}{rating_text}{address_text}

View your full wishlist with /wishlist"""
                }
            else:
                return {
                    "handled": True,
                    "response": f"❌ Error saving place: {result.get('error')}"
                }

        except Exception as e:
            print(f"Error handling Google Maps URL: {e}")
            return {
                "handled": True,
                "response": f"❌ Error processing Google Maps link: {str(e)}"
            }

    def _format_itinerary_summary(self, items: list) -> str:
        """
        Format itinerary items into readable day-by-day summary.

        Args:
            items: List of itinerary item dicts

        Returns:
            str: Formatted summary
        """
        # Group by day
        by_day = {}
        for item in items:
            day = item.get('day_order', 0)
            if day not in by_day:
                by_day[day] = []
            by_day[day].append(item)

        # Format each day
        summary_lines = []
        for day in sorted(by_day.keys()):
            day_items = by_day[day]
            summary_lines.append(f"\n**Day {day}:**")

            for item in sorted(day_items, key=lambda x: x.get('time_order', 0)):
                time = item.get('time', '')
                title = item.get('title', 'Activity')
                location = item.get('location', '')

                time_str = f"{time} - " if time else ""
                location_str = f" ({location})" if location else ""

                summary_lines.append(f"  • {time_str}{title}{location_str}")

        return "\n".join(summary_lines)
