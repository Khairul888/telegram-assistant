"""QA Agent for answering trip-related questions."""
from api.agents.base_agent import BaseAgent


class QAAgent(BaseAgent):
    """Agent for general trip questions using context retrieval."""

    def _define_tools(self) -> list:
        """QA agent doesn't use function calling - uses context-based Q&A."""
        return []

    async def process(self, user_id: str, chat_id: str, message: str,
                     trip_context: dict) -> dict:
        """
        Process question using trip context (travel events, expenses, etc.).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message: User question
            trip_context: Current trip dict

        Returns:
            dict: {"success": bool, "response": str, "already_sent": bool}
        """
        try:
            # Debug logging
            print(f"[QA Agent] Processing question for trip_id={trip_context['id']}, trip_name={trip_context.get('trip_name')}, chat_id={chat_id}")

            # Build comprehensive trip context
            context = await self._build_trip_context(trip_context['id'])

            # Debug: Log context length
            print(f"[QA Agent] Built context ({len(context)} chars): {context[:200]}...")

            # Generate response with context
            system_instruction = f"""You are a helpful travel assistant for "{trip_context['trip_name']}" to {trip_context.get('location', 'Unknown')}.

Use the following information to answer questions:

{context}

Answer the user's question based on this trip information. If you don't have the information, say so clearly. Use plain text without bold formatting."""

            # Determine if web search is needed
            needs_search = self._should_use_web_search(message)

            if needs_search:
                # Use search grounding for real-time information
                result = await self.gemini.generate_response_with_search(
                    message, system_instruction
                )
                response = result.get("response", "I couldn't find an answer.")
            else:
                # Standard generation without search
                response = await self.gemini.generate_response(message, system_instruction)

            return {"success": True, "response": response, "already_sent": False}

        except Exception as e:
            return {"success": False, "response": f"Error: {str(e)}", "already_sent": False}

    def _should_use_web_search(self, question: str) -> bool:
        """
        Determine if question needs web search for real-time information.

        Args:
            question: User's question text

        Returns:
            bool: True if web search should be used
        """
        # Keywords that indicate need for real-time web data
        search_keywords = [
            'weather', 'forecast', 'temperature',
            'recommend', 'best', 'top rated', 'popular',
            'current', 'now', 'today', 'tomorrow',
            'price', 'cost', 'how much',
            'hours', 'open', 'closed', 'operating',
            'events', 'happening', 'what to do',
            'traffic', 'busy', 'crowded'
        ]

        question_lower = question.lower()
        return any(keyword in question_lower for keyword in search_keywords)

    async def _build_trip_context(self, trip_id: int) -> str:
        """
        Build context string from trip data (travel events, expenses, etc.).

        Args:
            trip_id: Trip ID

        Returns:
            str: Formatted context string
        """
        trip_service = self.services.get('trip')
        if not trip_service:
            return "No trip data available"

        supabase = trip_service.supabase
        context_parts = []

        # Get travel events (flights, hotels)
        events_result = supabase.table('travel_events')\
            .select('*')\
            .eq('trip_id', trip_id)\
            .execute()

        # Debug logging
        print(f"[QA Agent] Queried travel_events for trip_id={trip_id}, found {len(events_result.data) if events_result.data else 0} events")
        if events_result.data:
            print(f"[QA Agent] First event: {events_result.data[0]}")

        if events_result.data:
            context_parts.append("TRAVEL INFORMATION:")
            for event in events_result.data:
                if event['event_type'] == 'flight':
                    flight_info = (
                        f"- Flight: {event.get('airline', 'Unknown airline')} "
                        f"{event.get('flight_number', '')} "
                        f"from {event.get('departure_city', 'Unknown')} "
                        f"to {event.get('arrival_city', 'Unknown')} "
                        f"departing {event.get('departure_time', 'Unknown time')}"
                    )
                    if event.get('seat'):
                        flight_info += f", seat {event['seat']}"
                    if event.get('gate'):
                        flight_info += f", gate {event['gate']}"
                    if event.get('departure_terminal'):
                        flight_info += f", departure terminal {event['departure_terminal']}"
                    if event.get('arrival_terminal'):
                        flight_info += f", arrival terminal {event['arrival_terminal']}"
                    context_parts.append(flight_info)

                elif event['event_type'] == 'hotel':
                    hotel_info = (
                        f"- Hotel: {event.get('hotel_name', 'Unknown hotel')} "
                        f"in {event.get('location', 'Unknown location')}, "
                        f"check-in {event.get('check_in_date', 'Unknown')} "
                        f"to check-out {event.get('check_out_date', 'Unknown')}"
                    )
                    if event.get('room_type'):
                        hotel_info += f", room type: {event['room_type']}"
                    context_parts.append(hotel_info)

        # Get expenses
        expenses_result = supabase.table('expenses')\
            .select('*')\
            .eq('trip_id', trip_id)\
            .execute()

        if expenses_result.data:
            context_parts.append("\nEXPENSE INFORMATION:")
            total_spent = sum(e.get('total_amount', 0) for e in expenses_result.data)
            context_parts.append(f"- Total spent: ${total_spent:.2f}")

            # Group by category
            by_category = {}
            for expense in expenses_result.data:
                category = expense.get('category', 'other')
                amount = expense.get('total_amount', 0)
                by_category[category] = by_category.get(category, 0) + amount

            for category, amount in by_category.items():
                context_parts.append(f"- {category.capitalize()}: ${amount:.2f}")

        # Get itinerary
        itinerary_result = supabase.table('trip_itinerary')\
            .select('*')\
            .eq('trip_id', trip_id)\
            .order('date')\
            .order('time_order')\
            .limit(20)\
            .execute()

        if itinerary_result.data:
            context_parts.append("\nITINERARY:")
            for item in itinerary_result.data:
                time_str = f"{item.get('time', '')} " if item.get('time') else ""
                location_str = f" at {item.get('location')}" if item.get('location') else ""
                itinerary_info = f"- {item.get('date', 'Unknown date')} {time_str}{item.get('title', 'Activity')}{location_str}"
                if item.get('description'):
                    itinerary_info += f" - {item['description']}"
                context_parts.append(itinerary_info)

        # Get places wishlist
        places_result = supabase.table('trip_places')\
            .select('*')\
            .eq('trip_id', trip_id)\
            .eq('visited', False)\
            .limit(15)\
            .execute()

        if places_result.data:
            context_parts.append("\nPLACES TO VISIT:")
            for place in places_result.data:
                rating_str = f" ⭐{place.get('rating')}" if place.get('rating') else ""
                address_str = f", {place.get('address')}" if place.get('address') else ""
                place_info = f"- {place.get('name')} ({place.get('category', 'other').title()}){rating_str}{address_str}"
                if place.get('notes'):
                    place_info += f" - {place['notes']}"
                context_parts.append(place_info)

        if not context_parts:
            return "No trip information available yet. Upload flight tickets, hotel bookings, or receipts to get started!"

        return "\n".join(context_parts)
