"""File upload handler for documents, photos, and receipts."""
from typing import Dict


class FileHandler:
    """Handles file uploads and interactive expense splitting flow."""

    def __init__(self, gemini_service, trip_service, expense_service,
                 settlement_service, telegram_utils, supabase):
        """
        Initialize with service dependencies.

        Args:
            gemini_service: GeminiService instance
            trip_service: TripService instance
            expense_service: ExpenseService instance
            settlement_service: SettlementService instance
            telegram_utils: TelegramUtils instance
            supabase: Supabase client
        """
        self.gemini = gemini_service
        self.trip_service = trip_service
        self.expense_service = expense_service
        self.settlement = settlement_service
        self.telegram = telegram_utils
        self.supabase = supabase

    async def handle_file_upload(self, message: dict, user_id: str, chat_id: str) -> Dict:
        """
        Handle file upload (photo or document).

        Args:
            message: Telegram message dict
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            dict: {"response": str or None, "keyboard": dict or None}
        """
        # Get current trip
        trip = await self.trip_service.get_current_trip(user_id)
        if not trip:
            return {
                "response": """❌ No active trip found!

Create a trip first: /new_trip <trip name>""",
                "keyboard": None
            }

        # Extract file info
        file_info = self.telegram.extract_file_info(message)

        if not file_info["has_file"]:
            return {"response": "No file found in message.", "keyboard": None}

        try:
            # Download file
            file_data = await self.telegram.download_file(file_info["file_id"])

            # Route to appropriate processing method based on file type
            if file_info["file_type"] == "pdf":
                # Process PDF with Gemini File API
                result = await self.gemini.process_pdf(file_data)
            elif file_info["file_type"] in ["photo", "image_document"]:
                # Process image with Gemini Vision
                result = await self.gemini.process_document(file_data)
            else:
                # Unsupported file type
                return {
                    "response": f"❌ Unsupported file type: {file_info.get('mime_type', 'unknown')}. Please send images or PDFs.",
                    "keyboard": None
                }

            if not result.get("success"):
                return {
                    "response": f"❌ Could not process file: {result.get('error')}",
                    "keyboard": None
                }

            document_type = result.get("document_type")
            extracted_data = result.get("data", {})

            # Route based on document type
            if document_type == "receipt":
                return await self._handle_receipt(
                    user_id, chat_id, trip, extracted_data, file_info["file_name"]
                )
            elif document_type == "flight_ticket":
                return await self._handle_flight(
                    user_id, trip, extracted_data, file_info["file_name"]
                )
            elif document_type == "hotel_booking":
                return await self._handle_hotel(
                    user_id, trip, extracted_data, file_info["file_name"]
                )
            else:
                return await self._handle_generic_document(
                    user_id, trip, document_type, extracted_data, file_info["file_name"]
                )

        except Exception as e:
            return {
                "response": f"❌ Error processing file: {str(e)}",
                "keyboard": None
            }

    async def _handle_receipt(self, user_id: str, chat_id: str, trip: dict,
                             receipt_data: dict, file_name: str) -> Dict:
        """Handle receipt upload and create expense."""
        total = receipt_data.get("total", 0)
        merchant = receipt_data.get("merchant_name", "Unknown")
        date = receipt_data.get("date", "Unknown date")

        # Create expense record (without split info)
        expense_result = await self.expense_service.create_expense_from_receipt(
            user_id, trip['id'], receipt_data
        )

        if not expense_result.get("success"):
            return {
                "response": f"❌ Error creating expense: {expense_result.get('error')}",
                "keyboard": None
            }

        expense_id = expense_result['expense_id']

        # Store expense info in session for later use
        await self.trip_service.get_or_update_session(
            user_id,
            state='awaiting_receipt_payer',
            context={
                'expense_id': expense_id,
                'expense_amount': total,
                'expense_description': merchant,
                'trip_id': trip['id']
            }
        )

        # Create inline keyboard for "who paid?" selection
        participants = trip.get('participants', [])
        keyboard = {
            "inline_keyboard": [
                [{"text": p, "callback_data": f"receipt_paid_by:{expense_id}:{p}"}]
                for p in participants
            ]
        }

        message_text = f"""✅ Receipt extracted!

🏪 {merchant}
💰 Total: ${total:.2f}
📅 {date}

Who paid for this?"""

        # Send message with inline keyboard
        await self.telegram.send_message_with_keyboard(chat_id, message_text, keyboard)

        return {"response": None, "keyboard": None}  # Already sent

    async def _handle_flight(self, user_id: str, trip: dict,
                            flight_data: dict, file_name: str) -> Dict:
        """Handle flight ticket upload (supports multiple flights for round-trip/multi-city)."""
        try:
            # Check if flight_data contains multiple flights (new format)
            flights = flight_data.get("flights", [])

            # If no flights array, treat flight_data itself as a single flight (backwards compatibility)
            if not flights:
                flights = [flight_data]

            saved_flights = []

            # Insert each flight as a separate travel_event
            for flight in flights:
                event_data = {
                    "user_id": user_id,
                    "trip_id": trip['id'],
                    "event_type": "flight",
                    "airline": flight.get("airline"),
                    "flight_number": flight.get("flight_number"),
                    "departure_city": flight.get("departure_city"),
                    "departure_airport": flight.get("departure_airport"),
                    "departure_terminal": flight.get("departure_terminal"),
                    "arrival_city": flight.get("arrival_city"),
                    "arrival_airport": flight.get("arrival_airport"),
                    "arrival_terminal": flight.get("arrival_terminal"),
                    "departure_time": f"{flight.get('departure_date')} {flight.get('departure_time')}" if flight.get('departure_date') else None,
                    "arrival_time": f"{flight.get('arrival_date')} {flight.get('arrival_time')}" if flight.get('arrival_date') else None,
                    "gate": flight.get("gate"),
                    "seat": flight.get("seat"),
                    "booking_reference": flight.get("booking_reference"),
                    "passenger_name": flight.get("passenger_name"),
                    "raw_extracted_data": flight
                }

                self.supabase.table('travel_events').insert(event_data).execute()
                saved_flights.append(flight)

            # Update trip activity
            await self.trip_service.update_trip_activity(trip['id'])

            # Build response message
            if len(saved_flights) == 1:
                # Single flight
                flight = saved_flights[0]

                # Build flight details with terminal info if available
                flight_details = []
                flight_details.append(f"✈️ {flight.get('airline', 'Unknown')} {flight.get('flight_number', '')}")
                flight_details.append(f"📍 {flight.get('departure_city', 'Unknown')} → {flight.get('arrival_city', 'Unknown')}")

                if flight.get('departure_terminal') or flight.get('arrival_terminal'):
                    dep_term = flight.get('departure_terminal', 'N/A')
                    arr_term = flight.get('arrival_terminal', 'N/A')
                    flight_details.append(f"🏢 Terminal: {dep_term} → {arr_term}")

                flight_details.append(f"🕐 Departure: {flight.get('departure_date', '')} {flight.get('departure_time', '')}")
                flight_details.append(f"💺 Seat: {flight.get('seat', 'N/A')}")

                response_msg = f"""✅ Flight saved for {trip['trip_name']}!

{chr(10).join(flight_details)}

Ask me "when's my flight?" anytime!"""
            else:
                # Multiple flights (round-trip or multi-city)
                flight_summaries = []
                for idx, flight in enumerate(saved_flights, 1):
                    label = "Outbound" if idx == 1 else ("Return" if idx == 2 and len(saved_flights) == 2 else f"Flight {idx}")

                    # Build flight summary with terminal info if available
                    summary_parts = [
                        f"{label}: {flight.get('departure_city', 'Unknown')} → {flight.get('arrival_city', 'Unknown')}",
                        f"   {flight.get('airline', 'Unknown')} {flight.get('flight_number', '')}"
                    ]

                    # Add terminal info if available
                    if flight.get('departure_terminal') or flight.get('arrival_terminal'):
                        dep_term = flight.get('departure_terminal', 'N/A')
                        arr_term = flight.get('arrival_terminal', 'N/A')
                        summary_parts.append(f"   Terminal: {dep_term} → {arr_term}")

                    summary_parts.append(f"   {flight.get('departure_date', '')} {flight.get('departure_time', '')}")

                    flight_summaries.append("\n".join(summary_parts))

                response_msg = f"""✅ {len(saved_flights)} flights saved for {trip['trip_name']}!

{chr(10).join(flight_summaries)}

Ask me "when's my flight?" anytime!"""

            return {
                "response": response_msg,
                "keyboard": None
            }
        except Exception as e:
            return {
                "response": f"❌ Error saving flight: {str(e)}",
                "keyboard": None
            }

    async def _handle_hotel(self, user_id: str, trip: dict,
                           hotel_data: dict, file_name: str) -> Dict:
        """Handle hotel booking upload."""
        try:
            # Store in travel_events table
            event_data = {
                "user_id": user_id,
                "trip_id": trip['id'],
                "event_type": "hotel",
                "hotel_name": hotel_data.get("hotel_name"),
                "location": hotel_data.get("location"),
                "check_in_date": hotel_data.get("check_in_date"),
                "check_out_date": hotel_data.get("check_out_date"),
                "room_type": hotel_data.get("room_type"),
                "nights": hotel_data.get("nights"),
                "guests": hotel_data.get("guests"),
                "booking_reference": hotel_data.get("booking_reference"),
                "guest_name": hotel_data.get("guest_name"),
                "raw_extracted_data": hotel_data
            }

            self.supabase.table('travel_events').insert(event_data).execute()

            # Update trip activity
            await self.trip_service.update_trip_activity(trip['id'])

            hotel_name = hotel_data.get("hotel_name", "Unknown hotel")
            location = hotel_data.get("location", "Unknown location")
            check_in = hotel_data.get("check_in_date", "")
            check_out = hotel_data.get("check_out_date", "")
            nights = hotel_data.get("nights", 0)

            return {
                "response": f"""✅ Hotel saved for {trip['trip_name']}!

🏨 {hotel_name}
📍 {location}
📅 {check_in} → {check_out} ({nights} nights)
🛏️ Room: {hotel_data.get('room_type', 'N/A')}

Ask me "where are we staying?" anytime!""",
                "keyboard": None
            }
        except Exception as e:
            return {
                "response": f"❌ Error saving hotel: {str(e)}",
                "keyboard": None
            }

    async def _handle_generic_document(self, user_id: str, trip: dict,
                                      doc_type: str, data: dict, file_name: str) -> Dict:
        """Handle generic document upload."""
        try:
            # Store in documents table
            document_data = {
                "user_id": user_id,
                "trip_id": trip['id'],
                "file_id": f"{user_id}_{file_name}",
                "original_filename": file_name,
                "file_type": doc_type,
                "metadata_json": data,
                "processing_status": "completed"
            }

            self.supabase.table('documents').insert(document_data).execute()

            # Update trip activity
            await self.trip_service.update_trip_activity(trip['id'])

            return {
                "response": f"""✅ Document saved for {trip['trip_name']}!

📄 {file_name}
📁 Type: {doc_type}

You can ask me questions about this document later.""",
                "keyboard": None
            }
        except Exception as e:
            return {
                "response": f"❌ Error saving document: {str(e)}",
                "keyboard": None
            }

    async def handle_receipt_paid_by_callback(self, user_id: str, chat_id: str,
                                             expense_id: int, paid_by: str) -> Dict:
        """
        Handle receipt "who paid" selection. Now asks who is involved.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            expense_id: Expense ID
            paid_by: Name of person who paid

        Returns:
            dict: {"response": str or None, "keyboard": dict or None}
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id)
        context = session.get('conversation_context', {})

        amount = context.get('expense_amount')
        description = context.get('expense_description')
        trip_id = context.get('trip_id')

        # Get trip to get participants
        trip = await self.trip_service.get_current_trip(user_id)
        if not trip:
            return {"response": "Error: Trip not found", "keyboard": None}

        participants = trip.get('participants', [])

        # Update session with paid_by and move to participant selection
        context['paid_by'] = paid_by
        context['participants_selected'] = []
        await self.trip_service.get_or_update_session(
            user_id,
            state='awaiting_expense_participants',
            context=context
        )

        # Create keyboard for participant selection (multi-select)
        keyboard = {
            "inline_keyboard": [
                [{"text": f"☐ {p}", "callback_data": f"participant_toggle:{expense_id}:{p}"}]
                for p in participants
            ] + [
                [{"text": "✅ Done", "callback_data": f"participants_done:{expense_id}"}]
            ]
        }

        message = f"""💰 ${amount:.2f} - {description}
👤 Paid by: {paid_by}

Who is involved in this expense?
Select all who should split this expense:"""

        # Send message with keyboard
        await self.telegram.send_message_with_keyboard(chat_id, message, keyboard)

        return {"response": None, "keyboard": None}
