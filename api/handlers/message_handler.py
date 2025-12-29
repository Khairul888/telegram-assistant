"""Message handler for Q&A with trip context."""


class MessageHandler:
    """Handles conversational Q&A with trip-scoped context."""

    def __init__(self, gemini_service, trip_service, supabase):
        """
        Initialize with service dependencies.

        Args:
            gemini_service: GeminiService instance
            trip_service: TripService instance
            supabase: Supabase client
        """
        self.gemini = gemini_service
        self.trip_service = trip_service
        self.supabase = supabase

    async def handle_question(self, user_id: str, question_text: str) -> str:
        """
        Handle user question with trip-scoped context.

        Args:
            user_id: Telegram user ID
            question_text: User's question

        Returns:
            str: AI-generated response based on trip context
        """
        # Get current trip
        trip = await self.trip_service.get_current_trip(user_id)

        if not trip:
            return """I don't have any trip context yet.

Create a trip with: /new_trip <trip name>

Then upload flight tickets, hotel bookings, or other documents and I'll remember them!"""

        # Build context from current trip's data
        context = await self._build_trip_context(trip['id'])

        # Generate AI response with context
        system_instruction = f"""You are a helpful travel assistant for a trip called "{trip['trip_name']}" to {trip.get('location', 'Unknown')}.

Use the following information to answer questions:

{context}

Answer the user's question based on this trip information. If you don't have the information, say so clearly. Use plain text without bold formatting."""

        # Determine if web search is needed
        needs_search = await self._should_use_web_search(question_text)

        if needs_search:
            # Use search grounding for real-time information
            result = await self.gemini.generate_response_with_search(
                question_text, system_instruction
            )
            response = result.get("response", "I couldn't find an answer.")
        else:
            # Standard generation without search
            response = await self.gemini.generate_response(question_text, system_instruction)

        return response

    async def _should_use_web_search(self, question: str) -> bool:
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
        Build context string from trip documents and events.

        Args:
            trip_id: Trip ID

        Returns:
            str: Formatted context string
        """
        context_parts = []

        # Get travel events (flights, hotels)
        events_result = self.supabase.table('travel_events')\
            .select('*')\
            .eq('trip_id', trip_id)\
            .execute()

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
        expenses_result = self.supabase.table('expenses')\
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
        itinerary_result = self.supabase.table('trip_itinerary')\
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
        places_result = self.supabase.table('trip_places')\
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

        # Get documents
        docs_result = self.supabase.table('documents')\
            .select('*')\
            .eq('trip_id', trip_id)\
            .limit(5)\
            .execute()

        if docs_result.data:
            context_parts.append("\nOTHER DOCUMENTS:")
            for doc in docs_result.data:
                doc_info = f"- {doc.get('original_filename', 'Unknown')} ({doc.get('file_type', 'unknown type')})"
                if doc.get('overarching_theme'):
                    doc_info += f": {doc['overarching_theme']}"
                context_parts.append(doc_info)

        if not context_parts:
            return "No trip information available yet. Upload flight tickets, hotel bookings, or receipts to get started!"

        return "\n".join(context_parts)
