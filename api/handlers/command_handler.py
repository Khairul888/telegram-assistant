"""Command handler for bot commands."""
from typing import Dict


class CommandHandler:
    """Handles bot commands and multi-step conversation flows."""

    def __init__(self, trip_service, expense_service, settlement_service, telegram_utils=None,
                 itinerary_service=None, places_service=None):
        """
        Initialize with service dependencies.

        Args:
            trip_service: TripService instance
            expense_service: ExpenseService instance
            settlement_service: SettlementService instance
            telegram_utils: TelegramUtils instance (optional, for inline keyboards)
            itinerary_service: ItineraryService instance (optional, for itinerary commands)
            places_service: PlacesService instance (optional, for places commands)
        """
        self.trip_service = trip_service
        self.expense_service = expense_service
        self.settlement_service = settlement_service
        self.telegram_utils = telegram_utils
        self.itinerary_service = itinerary_service
        self.places_service = places_service

    async def handle_new_trip(self, user_id: str, chat_id: str, chat_type: str, message_text: str) -> str:
        """
        Handle /new_trip command - start trip creation flow.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID (group ID or user ID for DMs)
            chat_type: Chat type (private, group, supergroup)
            message_text: Full command message

        Returns:
            str: Response message
        """
        # Extract trip name from command
        parts = message_text.split(maxsplit=1)
        if len(parts) < 2:
            return """Please provide a trip name!

Usage: /new_trip Tokyo 2025

I'll then ask for location and participants."""

        trip_name = parts[1].strip()

        # Set conversation state to await location
        await self.trip_service.get_or_update_session(
            user_id,
            chat_id,
            state='awaiting_location',
            context={'trip_name': trip_name, 'chat_type': chat_type}
        )

        if chat_type in ['group', 'supergroup']:
            return f"""Great! Creating trip: "{trip_name}" for this group.

Where are you traveling to? (e.g., "Tokyo, Japan")

Note: All group members will be able to access and manage this trip!"""
        else:
            return f"""Great! Creating trip: "{trip_name}"

Where are you traveling to? (e.g., "Tokyo, Japan")"""

    async def handle_location_response(self, user_id: str, chat_id: str, location: str) -> str:
        """
        Handle location response during trip creation.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            location: Location text

        Returns:
            str: Response message
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})
        trip_name = context.get('trip_name')

        if not trip_name:
            return "Error: Trip creation session expired. Please start over with /new_trip"

        # Update context and change state
        context['location'] = location
        await self.trip_service.get_or_update_session(
            user_id,
            chat_id,
            state='awaiting_participants',
            context=context
        )

        return f"""Location set: {location}

Who's on this trip? Send names separated by commas.
Example: Alice, Bob, Carol

(Include yourself if you want to track your expenses too!)"""

    async def handle_participants_response(self, user_id: str, chat_id: str, participants_text: str) -> str:
        """
        Handle participants response and create trip.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            participants_text: Comma-separated participant names

        Returns:
            str: Response message
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})
        trip_name = context.get('trip_name')
        location = context.get('location')
        chat_type = context.get('chat_type', 'private')

        if not trip_name or not location:
            return "Error: Trip creation session expired. Please start over with /new_trip"

        # Parse participants
        participants = [p.strip() for p in participants_text.split(',') if p.strip()]

        if not participants:
            return "Please provide at least one participant name."

        # Create trip
        result = await self.trip_service.create_trip(
            user_id, chat_id, chat_type, trip_name, location, participants
        )

        if result.get('success'):
            # Clear conversation state
            await self.trip_service.clear_conversation_state(user_id, chat_id)

            participants_list = '\n'.join([f"  • {p}" for p in participants])

            if chat_type in ['group', 'supergroup']:
                return f"""✅ Trip "{trip_name}" created for this group!

📍 Location: {location}
👥 Participants:
{participants_list}

All group members can now:
• Upload receipts and documents
• Add expenses with /add_expense
• Check balances with /balance
• View trips with /list_trips

This trip is now active. Switch between trips using /switch_trip"""
            else:
                return f"""✅ Trip "{trip_name}" created!

📍 Location: {location}
👥 Participants:
{participants_list}

This is now your active trip. Upload flight tickets, hotel bookings, or receipts and I'll track everything!

Commands:
• /balance - Check who owes what
• /list_trips - See all your trips
• /current_trip - View active trip details"""
        else:
            return f"❌ Error creating trip: {result.get('error')}"

    async def handle_expense_fields_response(self, user_id: str, chat_id: str, user_input: str) -> str:
        """
        Handle user response when expense is missing required fields.
        Continues the expense creation with the new information.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            user_input: User's response text

        Returns:
            str: Response message (success or further prompt)
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})
        incomplete_expense = context.get('incomplete_expense', {})
        missing_fields = context.get('missing_fields', [])
        trip_id = context.get('trip_id')

        if not incomplete_expense or not trip_id:
            # Session expired
            await self.trip_service.clear_conversation_state(user_id, chat_id)
            return "The expense session has expired. Please start over by telling me about the expense."

        # Get trip info for context
        trip = await self.trip_service.get_trip_by_id(trip_id)
        trip_participants = trip.get('participants', []) if trip else []

        # Try to fill in missing fields from user input
        user_input_lower = user_input.lower().strip()

        # Determine what field to fill based on what's missing
        if 'merchant_name' in missing_fields:
            # User is providing the description/merchant name
            incomplete_expense['merchant_name'] = user_input
            missing_fields.remove('merchant_name')

        elif 'split_between' in missing_fields or 'paid_by' in missing_fields:
            # User is providing expense split information (possibly combined with payer info)
            # Use AI to parse the natural language response
            from api.services.gemini_service import GeminiService
            gemini = GeminiService()

            # Build prompt for AI to extract information
            participants_str = ', '.join(trip_participants) if trip_participants else 'No participants set'
            prompt = f"""Parse this expense split information and extract who paid and who to split with.

Trip participants: {participants_str}

User said: "{user_input}"

Extract:
1. Who paid (the payer's name)
2. List of people to split the expense between

Rules:
- If user says "everyone", "all", "split evenly", etc., include ALL trip participants
- If user mentions specific names, use only those names
- The payer should always be included in the split list
- Return names exactly as they appear in the trip participants list when possible
- If a name isn't in the participants list, use the name as provided by the user

Return a JSON object with:
- "paid_by": the payer's name (string)
- "split_between": array of participant names

Example responses:
Input: "Khairul paid, split evenly amongst everyone"
Output: {{"paid_by": "Khairul", "split_between": ["Khairul", "Alice", "Bob"]}}

Input: "Alice paid, split with Bob and Carol"
Output: {{"paid_by": "Alice", "split_between": ["Alice", "Bob", "Carol"]}}

Input: "split with everyone" (if paid_by is already known)
Output: {{"split_between": ["Khairul", "Alice", "Bob"]}}"""

            result = await gemini.generate_response(prompt, system_instruction="You are a JSON extractor. Return only valid JSON, no other text.")

            try:
                import json
                import re
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())

                    # Fill in paid_by if extracted and missing
                    if 'paid_by' in missing_fields and parsed.get('paid_by'):
                        incomplete_expense['paid_by'] = parsed['paid_by']
                        missing_fields.remove('paid_by')

                    # Fill in split_between if extracted and missing
                    if 'split_between' in missing_fields and parsed.get('split_between'):
                        incomplete_expense['split_between'] = parsed['split_between']
                        missing_fields.remove('split_between')
                else:
                    # Fallback to simple comma parsing
                    participants = [p.strip() for p in user_input.split(',') if p.strip()]
                    if not participants:
                        participants = [user_input]

                    if 'split_between' in missing_fields:
                        incomplete_expense['split_between'] = participants
                        missing_fields.remove('split_between')
                    elif 'paid_by' in missing_fields:
                        incomplete_expense['paid_by'] = participants[0] if participants else user_input
                        missing_fields.remove('paid_by')

            except Exception as e:
                print(f"Error parsing expense split info: {e}")
                # Fallback to simple parsing
                if 'split_between' in missing_fields:
                    participants = [p.strip() for p in user_input.split(',') if p.strip()]
                    if not participants:
                        participants = [user_input]
                    incomplete_expense['split_between'] = participants
                    missing_fields.remove('split_between')
                elif 'paid_by' in missing_fields:
                    incomplete_expense['paid_by'] = user_input
                    missing_fields.remove('paid_by')

        elif 'total_amount' in missing_fields:
            # User is providing the amount
            # Extract number from input
            import re
            amount_match = re.search(r'[\d.]+', user_input)
            if amount_match:
                incomplete_expense['total_amount'] = float(amount_match.group())
                missing_fields.remove('total_amount')
            else:
                return "I couldn't understand the amount. Please provide a number (e.g., 50, 123.45)"

        # Check if we still have missing fields
        if missing_fields:
            # Update session with filled data and remaining missing fields
            await self.trip_service.get_or_update_session(
                user_id=user_id,
                chat_id=chat_id,
                state='awaiting_expense_fields',
                context={
                    'incomplete_expense': incomplete_expense,
                    'missing_fields': missing_fields,
                    'trip_id': trip_id
                }
            )

            # Prompt for next missing field
            field_prompts = {
                'total_amount': "the amount spent",
                'paid_by': "who paid",
                'merchant_name': "what it was for (description)",
                'split_between': "who should split this expense"
            }

            next_field = missing_fields[0]
            return f"Got it! Now I need to know {field_prompts.get(next_field, next_field)}."

        # All fields filled, create the expense
        result = await self.expense_service.create_expense(
            user_id=user_id,
            trip_id=trip_id,
            merchant_name=incomplete_expense.get('merchant_name', 'Expense'),
            total_amount=float(incomplete_expense.get('total_amount')),
            category=incomplete_expense.get('category', 'other'),
            paid_by=incomplete_expense.get('paid_by'),
            split_between=incomplete_expense.get('split_between')
        )

        # Clear conversation state
        await self.trip_service.clear_conversation_state(user_id, chat_id)

        if result.get('success'):
            expense = result.get('expense', {})
            merchant = expense.get('merchant_name', 'Unknown')
            amount = expense.get('total_amount', 0)
            date = expense.get('transaction_date', 'Unknown date')
            paid_by = expense.get('paid_by', 'Unknown')
            split_between = expense.get('split_between', [])

            response = f"""Expense added!

💰 {merchant} - ${amount:.2f}
📅 {date}
👤 Paid by: {paid_by}"""

            if split_between:
                response += f"\n👥 Split with: {', '.join(split_between)}"

            return response
        else:
            return f"❌ Error creating expense: {result.get('error')}"

    async def handle_list_trips(self, user_id: str, chat_id: str) -> str:
        """
        Handle /list_trips command.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            str: Response message with trip list
        """
        trips = await self.trip_service.list_trips(user_id, chat_id)

        if not trips:
            return """You don't have any trips yet!

Create one with: /new_trip <trip name>

Example: /new_trip Paris 2025"""

        current_trip = await self.trip_service.get_current_trip(user_id, chat_id)
        current_id = current_trip['id'] if current_trip else None

        trips_text = []
        for trip in trips:
            is_current = "🟢" if trip['id'] == current_id else "⚪"
            participants = trip.get('participants', [])
            participants_count = len(participants) if isinstance(participants, list) else 0
            status = trip.get('status', 'active')

            trips_text.append(
                f"{is_current} {trip['trip_name']}\n"
                f"   📍 {trip.get('location', 'Unknown')}\n"
                f"   👥 {participants_count} participants | {status}"
            )

        return "Your trips:\n\n" + "\n\n".join(trips_text)

    async def handle_current_trip(self, user_id: str, chat_id: str) -> str:
        """
        Handle /current_trip command.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            str: Response message with current trip details
        """
        trip = await self.trip_service.get_current_trip(user_id, chat_id)

        if not trip:
            return """No active trip found.

Create one with: /new_trip <trip name>"""

        participants = trip.get('participants', [])
        participants_list = '\n'.join([
            f"  • {p}" for p in (participants if isinstance(participants, list) else [])
        ])

        # Get expense summary
        summary = await self.expense_service.get_trip_expenses_summary(trip['id'])

        created_date = trip.get('created_at', '')[:10] if trip.get('created_at') else 'Unknown'

        return f"""Current trip: {trip['trip_name']}

📍 Location: {trip.get('location', 'Unknown')}
👥 Participants:
{participants_list}

💰 Expenses:
  • Total spent: ${summary.get('total_spent', 0):.2f}
  • Number of expenses: {summary.get('expense_count', 0)}

Status: {trip.get('status', 'active')}
Created: {created_date}

Use /balance to see settlement details."""

    async def handle_balance(self, user_id: str, chat_id: str) -> str:
        """
        Handle /balance command - show running balance.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            str: Response message with settlement details
        """
        trip = await self.trip_service.get_current_trip(user_id, chat_id)

        if not trip:
            return "No active trip. Create one with /new_trip"

        balance = await self.settlement_service.calculate_running_balance(trip['id'])

        # Get summary
        summary = await self.expense_service.get_trip_expenses_summary(trip['id'])

        return f"""💰 Running Balance: {trip['trip_name']}

Total spent: ${summary.get('total_spent', 0):.2f}
Expenses: {summary.get('expense_count', 0)}

Settlement:
{balance}

This shows the total owed across all expenses for this trip."""

    async def handle_switch_trip(self, user_id: str, chat_id: str, message_text: str) -> str:
        """
        Handle /switch_trip command for context switching between trips.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message_text: Full message text including command

        Returns:
            str: Response message with trip list or switch confirmation
        """
        trips = await self.trip_service.list_trips(user_id, chat_id)
        if not trips:
            return "No trips in this chat. Create one with /new_trip"

        parts = message_text.split(maxsplit=1)

        if len(parts) == 1:
            # Show list with IDs
            current = await self.trip_service.get_current_trip(user_id, chat_id)
            current_id = current['id'] if current else None

            trips_text = []
            for trip in trips:
                marker = "🟢" if trip['id'] == current_id else "⚪"
                participants_count = len(trip.get('participants', []))
                trips_text.append(
                    f"{marker} ID: {trip['id']} - {trip['trip_name']}\n"
                    f"   📍 {trip.get('location', 'Unknown')} | "
                    f"👥 {participants_count} people"
                )

            return f"""Select trip to activate:

{chr(10).join(trips_text)}

Use: /switch_trip <ID>"""

        else:
            # Switch to specified trip
            try:
                trip_id = int(parts[1].strip())
            except ValueError:
                return "Invalid trip ID. Use: /switch_trip <ID>"

            result = await self.trip_service.switch_trip(user_id, chat_id, trip_id)

            if result['success']:
                trip = result['trip']
                participants_count = len(trip.get('participants', []))
                return f"""Switched to: {trip['trip_name']}

📍 {trip.get('location')}
👥 {participants_count} participants

All commands now operate on this trip."""
            else:
                return f"Error: {result.get('error')}"

    async def handle_start(self) -> str:
        """Handle /start command."""
        return """Welcome to your Travel Assistant! ✈️

I help you:
✈️ Remember trip details (flights, hotels)
💰 Track expenses and split bills

Getting Started:
1. Create a trip: /new_trip <trip name>
2. Upload flight tickets or hotel bookings
3. Upload receipts to track expenses

Commands:
• /new_trip <name> - Start a new trip
• /list_trips - See all your trips
• /current_trip - View active trip
• /balance - Check who owes what
• /help - Show this message"""

    async def handle_help(self, chat_type: str = 'private') -> str:
        """Handle /help command with chat-type aware messaging.

        Args:
            chat_type: Chat type (private, group, supergroup)
        """
        base_help = """📚 Commands Guide:

TRIPS:
• /new_trip <name> - Create new trip
  Example: /new_trip Tokyo 2025
• /list_trips - View all trips"""

        if chat_type in ['group', 'supergroup']:
            base_help += """
• /switch_trip [ID] - Switch active trip for this group
• /current_trip - Show active trip details"""
        else:
            base_help += """
• /current_trip - Show active trip details"""

        base_help += """

EXPENSES:
• /add_expense <amount> <description> - Add expense manually
  Example: /add_expense 50.00 Dinner at restaurant
• /list_expenses - View all expenses for current trip
• Upload receipt photo → I'll extract details & ask how to split
• /balance - See running balance and settlements

TRAVEL INFO:
• Upload flight ticket → I'll remember details
• Upload hotel booking → I'll save check-in dates
• /itinerary - View trip schedule
• /wishlist - See places to visit

OTHER:
• /start - Welcome message
• /help - This guide

Tips:"""

        if chat_type in ['group', 'supergroup']:
            base_help += """
  - Any group member can create and access trips
  - Use /switch_trip to change active trip
  - Participants are simple names (not Telegram accounts)
  - Latest trip is automatically active

💬 HOW TO TALK TO ME IN GROUPS:
  - Commands work directly: Just type /balance or /add_expense
  - Multi-step commands: @mention me or reply to my messages
    Example: /new_trip Tokyo → then @mention "Tokyo, Japan" for location
  - Natural language needs @mention: "@bot_name I paid $50 for coffee"
  - Or reply to my messages for natural conversations
  - I'll ignore regular chat so I don't spam the group!"""
        else:
            base_help += """
  - Latest trip is automatically active
  - All uploads are linked to current trip
  - Use simple names for participants (no Telegram accounts needed)"""

        return base_help

    async def handle_add_expense(self, user_id: str, chat_id: str, message_text: str) -> Dict:
        """
        Handle /add_expense command - start manual expense entry flow.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message_text: Full command message

        Returns:
            dict: {"response": str or None, "keyboard": dict or None}
        """
        # Check active trip
        trip = await self.trip_service.get_current_trip(user_id, chat_id)
        if not trip:
            return {
                "response": """No active trip found!

Create a trip first: /new_trip <trip name>""",
                "keyboard": None
            }

        # Parse command: /add_expense 50.00 Dinner at restaurant
        parts = message_text.split(maxsplit=2)
        if len(parts) < 3:
            return {
                "response": """Please provide amount and description!

Usage: /add_expense <amount> <description>

Examples:
• /add_expense 50.00 Dinner at restaurant
• /add_expense 15.50 Taxi to airport
• /add_expense 100 Hotel tip""",
                "keyboard": None
            }

        try:
            amount = float(parts[1])
            description = parts[2].strip()
        except ValueError:
            return {
                "response": "Invalid amount. Please use a number like: 50.00",
                "keyboard": None
            }

        if amount <= 0:
            return {
                "response": "Amount must be greater than 0",
                "keyboard": None
            }

        # Create expense record immediately (will be updated with split info later)
        from datetime import datetime
        result = await self.expense_service.create_expense(
            user_id=user_id,
            trip_id=trip['id'],
            merchant_name=description,
            total_amount=amount,
            transaction_date=datetime.now().date().isoformat()
        )

        if not result.get("success"):
            return {
                "response": f"Error creating expense: {result.get('error')}",
                "keyboard": None
            }

        expense_id = result['expense_id']

        # Store in session context
        await self.trip_service.get_or_update_session(
            user_id,
            state='awaiting_expense_payer',
            context={
                'expense_id': expense_id,
                'expense_amount': amount,
                'expense_description': description,
                'trip_id': trip['id']
            }
        )

        # Create keyboard for selecting who paid
        participants = trip.get('participants', [])
        if not isinstance(participants, list) or not participants:
            return {
                "response": "No participants in trip. Please add participants when creating the trip.",
                "keyboard": None
            }

        keyboard = {
            "inline_keyboard": [
                [{"text": p, "callback_data": f"expense_paid_by:{p}"}]
                for p in participants
            ]
        }

        # Send message with keyboard
        if self.telegram_utils:
            message = f"""💰 Adding expense: ${amount:.2f}
📝 {description}

Who paid for this?"""
            await self.telegram_utils.send_message_with_keyboard(chat_id, message, keyboard)
            return {"response": None, "keyboard": None}  # Already sent
        else:
            # Fallback if no telegram_utils
            participants_list = ', '.join(participants)
            return {
                "response": f"""Adding expense: ${amount:.2f} - {description}

Who paid? Reply with one of: {participants_list}""",
                "keyboard": None
            }

    async def handle_expense_payer_callback(self, user_id: str, chat_id: str, paid_by: str) -> Dict:
        """
        Handle callback when user selects who paid for manual expense.
        Now asks who is involved in the expense.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            paid_by: Name of person who paid

        Returns:
            dict: {response: str or None, keyboard: dict or None}
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})

        amount = context.get('expense_amount')
        description = context.get('expense_description')
        trip_id = context.get('trip_id')
        expense_id = context.get('expense_id')

        if not all([amount, description, trip_id]):
            return {"response": "Error: Expense session expired. Please start over with /add_expense", "keyboard": None}

        # Get trip to get participants
        trip = await self.trip_service.get_current_trip(user_id, chat_id)
        if not trip:
            return {"response": "Error: Trip not found", "keyboard": None}

        participants = trip.get('participants', [])

        # Update session with paid_by and move to participant selection
        context['paid_by'] = paid_by
        context['participants_selected'] = []  # Track selected participants
        await self.trip_service.get_or_update_session(
            user_id,
            chat_id,
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
        if self.telegram_utils:
            await self.telegram_utils.send_message_with_keyboard(chat_id, message, keyboard)
            return {"response": None, "keyboard": None}
        else:
            return {"response": message, "keyboard": None}

    async def handle_participant_toggle_callback(self, user_id: str, chat_id: str,
                                                 message_id: int, expense_id: int,
                                                 participant: str) -> Dict:
        """
        Handle participant selection toggle (multi-select).

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message_id: Message ID to edit
            expense_id: Expense ID
            participant: Participant name to toggle

        Returns:
            dict: {response: str or None, keyboard: dict or None}
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})

        participants_selected = context.get('participants_selected', [])
        amount = context.get('expense_amount')
        description = context.get('expense_description')
        paid_by = context.get('paid_by')

        # Toggle selection
        if participant in participants_selected:
            participants_selected.remove(participant)
        else:
            participants_selected.append(participant)

        # Update session
        context['participants_selected'] = participants_selected
        await self.trip_service.get_or_update_session(user_id, chat_id, context=context)

        # Get trip for all participants
        trip = await self.trip_service.get_current_trip(user_id, chat_id)
        all_participants = trip.get('participants', [])

        # Rebuild keyboard with updated checkboxes
        keyboard = {
            "inline_keyboard": [
                [{"text": f"{'☑' if p in participants_selected else '☐'} {p}",
                  "callback_data": f"participant_toggle:{expense_id}:{p}"}]
                for p in all_participants
            ] + [
                [{"text": "✅ Done", "callback_data": f"participants_done:{expense_id}"}]
            ]
        }

        message = f"""💰 ${amount:.2f} - {description}
👤 Paid by: {paid_by}

Who is involved in this expense?
Select all who should split this expense:"""

        # Edit message with updated keyboard
        if self.telegram_utils:
            await self.telegram_utils.edit_message_keyboard(chat_id, message_id, message, keyboard)

        return {"response": None, "keyboard": None}

    async def handle_participants_done_callback(self, user_id: str, chat_id: str,
                                                expense_id: int) -> Dict:
        """
        Handle completion of participant selection. Ask for split type.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            expense_id: Expense ID

        Returns:
            dict: {response: str or None, keyboard: dict or None}
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})

        participants_selected = context.get('participants_selected', [])
        amount = context.get('expense_amount')
        description = context.get('expense_description')
        paid_by = context.get('paid_by')

        if not participants_selected:
            return {"response": "Please select at least one participant.", "keyboard": None}

        # Update state to split type selection
        await self.trip_service.get_or_update_session(
            user_id,
            chat_id,
            state='awaiting_split_type',
            context=context
        )

        # Create keyboard for split type selection
        keyboard = {
            "inline_keyboard": [
                [{"text": "Equal Split", "callback_data": f"split_type:{expense_id}:equal"}],
                [{"text": "Custom Percentage", "callback_data": f"split_type:{expense_id}:percent"}],
                [{"text": "Custom Amounts", "callback_data": f"split_type:{expense_id}:amount"}]
            ]
        }

        participants_str = ', '.join(participants_selected)
        message = f"""💰 ${amount:.2f} - {description}
👤 Paid by: {paid_by}
👥 Split among: {participants_str}

How should this be split?"""

        # Send message with keyboard
        if self.telegram_utils:
            await self.telegram_utils.send_message_with_keyboard(chat_id, message, keyboard)
            return {"response": None, "keyboard": None}
        else:
            return {"response": message, "keyboard": None}

    async def handle_split_type_callback(self, user_id: str, chat_id: str,
                                        expense_id: int, split_type: str) -> Dict:
        """
        Handle split type selection.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            expense_id: Expense ID
            split_type: 'equal', 'percent', or 'amount'

        Returns:
            dict: {response: str or None, keyboard: dict or None}
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})

        participants_selected = context.get('participants_selected', [])
        amount = context.get('expense_amount')
        description = context.get('expense_description')
        paid_by = context.get('paid_by')
        trip_id = context.get('trip_id')

        if split_type == 'equal':
            # Equal split - complete immediately
            from datetime import datetime

            # Create or get expense
            if not expense_id:
                result = await self.expense_service.create_expense(
                    user_id=user_id,
                    trip_id=trip_id,
                    merchant_name=description,
                    total_amount=amount,
                    paid_by=paid_by,
                    split_between=participants_selected,
                    transaction_date=datetime.now().date().isoformat()
                )
                if not result.get("success"):
                    return {"response": f"Error creating expense: {result.get('error')}", "keyboard": None}
                expense_id = result['expense_id']

            # Update expense with even split
            update_result = await self.expense_service.update_expense_split(
                expense_id,
                paid_by,
                "even",
                participants_selected,
                amount
            )

            if not update_result.get("success"):
                return {"response": f"Error updating split: {update_result.get('error')}", "keyboard": None}

            # Calculate settlements
            split_amounts = update_result['expense']['split_amounts']
            immediate = self.settlement_service.calculate_immediate_settlement(
                amount, paid_by, split_amounts
            )
            running = await self.settlement_service.calculate_running_balance(trip_id)

            # Clear conversation state
            await self.trip_service.clear_conversation_state(user_id, chat_id)

            return {"response": f"""✅ Expense added!

💰 ${amount:.2f} - {description}
👤 Paid by: {paid_by}
👥 Split evenly among: {', '.join(participants_selected)}

📊 Immediate settlement (this expense):
{immediate}

📈 Running balance (all trip expenses):
{running}

Use /balance to see running balance anytime.""", "keyboard": None}

        elif split_type in ['percent', 'amount']:
            # Custom split - ask for amounts/percentages
            context['split_type'] = split_type
            context['custom_splits'] = {}
            context['current_participant_index'] = 0

            await self.trip_service.get_or_update_session(
                user_id,
                state='awaiting_custom_split',
                context=context
            )

            first_participant = participants_selected[0]
            split_unit = "%" if split_type == 'percent' else "$"

            return {"response": f"""Enter {first_participant}'s share as a number:

Example: {50 if split_type == 'percent' else round(amount / len(participants_selected), 2)}

(Total: ${amount:.2f})""", "keyboard": None}

        return {"response": "Invalid split type", "keyboard": None}

    async def handle_custom_split_text(self, user_id: str, chat_id: str, text: str) -> str:
        """
        Handle custom split amount/percentage text input.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            text: User input (number)

        Returns:
            str: Response message
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})

        participants_selected = context.get('participants_selected', [])
        split_type = context.get('split_type')
        custom_splits = context.get('custom_splits', {})
        current_index = context.get('current_participant_index', 0)
        amount = context.get('expense_amount')
        description = context.get('expense_description')
        paid_by = context.get('paid_by')
        trip_id = context.get('trip_id')
        expense_id = context.get('expense_id')

        # Parse input
        try:
            value = float(text.strip())
            if value < 0:
                return "Please enter a positive number."
        except ValueError:
            return "Invalid number. Please enter a valid amount."

        # Store split for current participant
        current_participant = participants_selected[current_index]
        custom_splits[current_participant] = value

        # Move to next participant
        current_index += 1

        if current_index < len(participants_selected):
            # Ask for next participant
            context['custom_splits'] = custom_splits
            context['current_participant_index'] = current_index
            await self.trip_service.get_or_update_session(user_id, context=context)

            next_participant = participants_selected[current_index]
            split_unit = "%" if split_type == 'percent' else "$"

            # Show progress
            if split_type == 'percent':
                total_so_far = sum(custom_splits.values())
                remaining = 100 - total_so_far
                progress = f"\nSo far: {total_so_far}% assigned, {remaining}% remaining"
            else:
                total_so_far = sum(custom_splits.values())
                remaining = amount - total_so_far
                progress = f"\nSo far: ${total_so_far:.2f} assigned, ${remaining:.2f} remaining"

            return f"""✅ {current_participant}: {value}{split_unit}{progress}

Enter {next_participant}'s share:"""

        else:
            # All participants done - validate and complete
            from datetime import datetime

            # Validate splits
            if split_type == 'percent':
                total = sum(custom_splits.values())
                if abs(total - 100) > 0.01:
                    return f"Error: Percentages must add up to 100%. Current total: {total}%"

                # Convert percentages to amounts
                split_amounts = {
                    p: round(amount * (pct / 100), 2)
                    for p, pct in custom_splits.items()
                }
            else:
                total = sum(custom_splits.values())
                if abs(total - amount) > 0.01:
                    return f"Error: Amounts must add up to ${amount:.2f}. Current total: ${total:.2f}"

                split_amounts = custom_splits

            # Create or get expense
            if not expense_id:
                result = await self.expense_service.create_expense(
                    user_id=user_id,
                    trip_id=trip_id,
                    merchant_name=description,
                    total_amount=amount,
                    paid_by=paid_by,
                    split_between=participants_selected,
                    transaction_date=datetime.now().date().isoformat()
                )
                if not result.get("success"):
                    return f"Error creating expense: {result.get('error')}"
                expense_id = result['expense_id']

            # Update expense with custom split
            update_result = await self.expense_service.update_expense_split(
                expense_id,
                paid_by,
                split_type,
                participants_selected,
                amount,
                split_amounts  # Pass the calculated split amounts
            )

            if not update_result.get("success"):
                return f"Error updating split: {update_result.get('error')}"

            # Calculate settlements
            immediate = self.settlement_service.calculate_immediate_settlement(
                amount, paid_by, split_amounts
            )
            running = await self.settlement_service.calculate_running_balance(trip_id)

            # Clear conversation state
            await self.trip_service.clear_conversation_state(user_id, chat_id)

            # Format split details
            split_details = '\n'.join([
                f"  • {p}: ${amt:.2f}" for p, amt in split_amounts.items()
            ])

            return f"""✅ Expense added with custom split!

💰 ${amount:.2f} - {description}
👤 Paid by: {paid_by}

Split breakdown:
{split_details}

📊 Immediate settlement (this expense):
{immediate}

📈 Running balance (all trip expenses):
{running}

Use /balance to see running balance anytime."""

    async def handle_list_expenses(self, user_id: str, chat_id: str) -> Dict:
        """
        Handle /list_expenses command - show all expenses for current trip.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            dict: {response: str or None, keyboard: dict or None}
        """
        trip = await self.trip_service.get_current_trip(user_id, chat_id)
        if not trip:
            return {
                "response": "No active trip. Create one with /new_trip",
                "keyboard": None
            }

        expenses = await self.expense_service.get_trip_expenses(trip['id'])

        if not expenses:
            return {
                "response": f"""No expenses found for {trip['trip_name']}.

Add expenses with /add_expense or upload a receipt!""",
                "keyboard": None
            }

        # Build expense list with action buttons
        message = f"Expenses for {trip['trip_name']}:\n\n"

        for idx, expense in enumerate(expenses, 1):
            amount = expense.get('total_amount', 0)
            merchant = expense.get('merchant_name', 'Unknown')
            paid_by = expense.get('paid_by', 'Unknown')
            date = expense.get('transaction_date', '')[:10] if expense.get('transaction_date') else 'No date'
            split_amounts = expense.get('split_amounts', {})

            message += f"{idx}. ${amount:.2f} - {merchant}\n"
            message += f"   Paid by: {paid_by} | Date: {date}\n"

            # Show split breakdown if available
            if split_amounts and isinstance(split_amounts, dict):
                message += f"   Split breakdown:\n"
                for person, owed_amount in split_amounts.items():
                    if person != paid_by:  # Don't show "owes" for the person who paid
                        message += f"     • {person} owes: ${owed_amount:.2f}\n"

            message += "\n"

        # Add buttons for each expense
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"#{i+1} Edit", "callback_data": f"edit_expense:{exp['id']}"},
                    {"text": f"#{i+1} Delete", "callback_data": f"delete_expense:{exp['id']}"}
                ]
                for i, exp in enumerate(expenses)
            ]
        }

        # Send message with keyboard
        if self.telegram_utils:
            await self.telegram_utils.send_message_with_keyboard(chat_id, message, keyboard)
            return {"response": None, "keyboard": None}
        else:
            return {"response": message, "keyboard": None}

    async def handle_delete_expense_callback(self, user_id: str, chat_id: str, expense_id: int) -> Dict:
        """
        Handle delete expense confirmation request.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            expense_id: Expense ID to delete

        Returns:
            dict: {response: str or None, keyboard: dict or None}
        """
        # Get expense details for confirmation
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return {"response": "Expense not found.", "keyboard": None}

        amount = expense.get('total_amount', 0)
        merchant = expense.get('merchant_name', 'Unknown')
        paid_by = expense.get('paid_by', 'Unknown')

        # Create confirmation keyboard
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "Yes, delete", "callback_data": f"confirm_delete:{expense_id}"},
                    {"text": "Cancel", "callback_data": f"cancel_delete:{expense_id}"}
                ]
            ]
        }

        message = f"""Are you sure you want to delete this expense?

${amount:.2f} - {merchant}
Paid by: {paid_by}

This cannot be undone."""

        # Send confirmation message
        if self.telegram_utils:
            await self.telegram_utils.send_message_with_keyboard(chat_id, message, keyboard)
            return {"response": None, "keyboard": None}
        else:
            return {"response": message, "keyboard": None}

    async def handle_confirm_delete_callback(self, user_id: str, chat_id: str, expense_id: int) -> str:
        """
        Handle confirmed expense deletion.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            expense_id: Expense ID to delete

        Returns:
            str: Response message
        """
        # Get expense details before deletion
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return "Expense not found."

        amount = expense.get('total_amount', 0)
        merchant = expense.get('merchant_name', 'Unknown')

        # Delete expense from database
        try:
            from api.utils.db_utils import get_supabase_client
            supabase = get_supabase_client()
            supabase.table('expenses').delete().eq('id', expense_id).execute()

            return f"""Expense deleted!

${amount:.2f} - {merchant}

Use /list_expenses to see remaining expenses."""
        except Exception as e:
            return f"Error deleting expense: {str(e)}"

    async def handle_cancel_delete_callback(self) -> str:
        """Handle cancelled expense deletion."""
        return "Deletion cancelled. Expense was not deleted."

    async def handle_edit_expense_callback(self, user_id: str, chat_id: str, expense_id: int) -> Dict:
        """
        Handle edit expense request - show edit options.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            expense_id: Expense ID to edit

        Returns:
            dict: {response: str or None, keyboard: dict or None}
        """
        # Get expense details
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return {"response": "Expense not found.", "keyboard": None}

        amount = expense.get('total_amount', 0)
        merchant = expense.get('merchant_name', 'Unknown')
        paid_by = expense.get('paid_by', 'Unknown')
        split_between = expense.get('split_between', [])
        split_amounts = expense.get('split_amounts', {})

        # Show current details and edit options
        split_list = '\n'.join([f"  • {p}: ${amt:.2f}" for p, amt in split_amounts.items()]) if split_amounts else "  Not split yet"

        message = f"""Edit expense:

${amount:.2f} - {merchant}
Paid by: {paid_by}
Split among: {', '.join(split_between) if split_between else 'None'}

Current split:
{split_list}

What would you like to edit?"""

        keyboard = {
            "inline_keyboard": [
                [{"text": "Change amount", "callback_data": f"edit_amount:{expense_id}"}],
                [{"text": "Change description", "callback_data": f"edit_description:{expense_id}"}],
                [{"text": "Change who paid", "callback_data": f"edit_payer:{expense_id}"}],
                [{"text": "Change split", "callback_data": f"edit_split:{expense_id}"}],
                [{"text": "Cancel", "callback_data": f"cancel_edit:{expense_id}"}]
            ]
        }

        # Send message with keyboard
        if self.telegram_utils:
            await self.telegram_utils.send_message_with_keyboard(chat_id, message, keyboard)
            return {"response": None, "keyboard": None}
        else:
            return {"response": message, "keyboard": None}

    async def handle_edit_amount_callback(self, user_id: str, chat_id: str, expense_id: int) -> str:
        """Handle edit amount request."""
        # Get current amount
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return "Expense not found."

        current_amount = expense.get('total_amount', 0)

        # Store in session
        await self.trip_service.get_or_update_session(
            user_id,
            chat_id,
            state='awaiting_edit_amount',
            context={'expense_id': expense_id}
        )

        return f"""Enter new amount:

Current: ${current_amount:.2f}

Reply with the new amount (e.g., 75.50)"""

    async def handle_edit_amount_text(self, user_id: str, chat_id: str, text: str) -> str:
        """Handle new amount text input."""
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})
        expense_id = context.get('expense_id')

        if not expense_id:
            return "Error: Edit session expired. Please start over."

        # Parse amount
        try:
            new_amount = float(text.strip())
            if new_amount <= 0:
                return "Amount must be greater than 0. Please enter a valid amount."
        except ValueError:
            return "Invalid amount. Please enter a number (e.g., 75.50)"

        # Get expense
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return "Expense not found."

        old_amount = expense.get('total_amount', 0)

        # Update expense amount
        from api.utils.db_utils import get_supabase_client
        supabase = get_supabase_client()

        # Update total_amount
        supabase.table('expenses').update({
            'total_amount': new_amount
        }).eq('id', expense_id).execute()

        # Recalculate split amounts if expense is already split
        split_between = expense.get('split_between', [])
        if split_between:
            per_person = new_amount / len(split_between)
            new_split_amounts = {p: round(per_person, 2) for p in split_between}
            supabase.table('expenses').update({
                'split_amounts': new_split_amounts
            }).eq('id', expense_id).execute()

        # Clear session
        await self.trip_service.clear_conversation_state(user_id, chat_id)

        return f"""Amount updated!

Old: ${old_amount:.2f}
New: ${new_amount:.2f}

Use /list_expenses to see updated expense."""

    async def handle_edit_description_callback(self, user_id: str, chat_id: str, expense_id: int) -> str:
        """Handle edit description request."""
        # Get current description
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return "Expense not found."

        current_description = expense.get('merchant_name', 'Unknown')

        # Store in session
        await self.trip_service.get_or_update_session(
            user_id,
            chat_id,
            state='awaiting_edit_description',
            context={'expense_id': expense_id}
        )

        return f"""Enter new description:

Current: {current_description}

Reply with the new description"""

    async def handle_edit_description_text(self, user_id: str, chat_id: str, text: str) -> str:
        """Handle new description text input."""
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id, chat_id)
        context = session.get('conversation_context', {})
        expense_id = context.get('expense_id')

        if not expense_id:
            return "Error: Edit session expired. Please start over."

        new_description = text.strip()
        if not new_description:
            return "Description cannot be empty. Please enter a description."

        # Get expense
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return "Expense not found."

        old_description = expense.get('merchant_name', 'Unknown')

        # Update expense description
        from api.utils.db_utils import get_supabase_client
        supabase = get_supabase_client()
        supabase.table('expenses').update({
            'merchant_name': new_description
        }).eq('id', expense_id).execute()

        # Clear session
        await self.trip_service.clear_conversation_state(user_id, chat_id)

        return f"""Description updated!

Old: {old_description}
New: {new_description}

Use /list_expenses to see updated expense."""

    async def handle_edit_payer_callback(self, user_id: str, chat_id: str, expense_id: int) -> Dict:
        """Handle edit payer request - show participant selection."""
        # Get expense and trip
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return {"response": "Expense not found.", "keyboard": None}

        trip_id = expense['trip_id']
        trip_result = await self.trip_service.get_current_trip(user_id, chat_id)

        # Also try to get trip by ID if current trip doesn't match
        if not trip_result or trip_result.get('id') != trip_id:
            from api.utils.db_utils import get_supabase_client
            supabase = get_supabase_client()
            trip_data = supabase.table('trips').select('*').eq('id', trip_id).execute()
            if trip_data.data:
                trip_result = trip_data.data[0]

        if not trip_result:
            return {"response": "Trip not found.", "keyboard": None}

        participants = trip_result.get('participants', [])
        current_payer = expense.get('paid_by', 'Unknown')

        # Store in session
        await self.trip_service.get_or_update_session(
            user_id,
            chat_id,
            state='awaiting_edit_payer',
            context={'expense_id': expense_id}
        )

        # Create keyboard
        keyboard = {
            "inline_keyboard": [
                [{"text": p, "callback_data": f"edit_payer_select:{expense_id}:{p}"}]
                for p in participants
            ]
        }

        message = f"""Select new payer:

Current payer: {current_payer}"""

        # Send message with keyboard
        if self.telegram_utils:
            await self.telegram_utils.send_message_with_keyboard(chat_id, message, keyboard)
            return {"response": None, "keyboard": None}
        else:
            return {"response": message, "keyboard": None}

    async def handle_edit_payer_select_callback(self, user_id: str, chat_id: str, expense_id: int, new_payer: str) -> str:
        """Handle payer selection for edit."""
        # Get expense
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return "Expense not found."

        old_payer = expense.get('paid_by', 'Unknown')

        # Update payer
        from api.utils.db_utils import get_supabase_client
        supabase = get_supabase_client()
        supabase.table('expenses').update({
            'paid_by': new_payer
        }).eq('id', expense_id).execute()

        # Clear session
        await self.trip_service.clear_conversation_state(user_id, chat_id)

        return f"""Payer updated!

Old: {old_payer}
New: {new_payer}

Use /list_expenses to see updated expense."""

    async def handle_edit_split_callback(self, user_id: str, chat_id: str, expense_id: int) -> Dict:
        """Handle edit split request - restart the split flow."""
        # Get expense
        expense = await self.expense_service.get_expense_by_id(expense_id)
        if not expense:
            return {"response": "Expense not found.", "keyboard": None}

        trip_id = expense['trip_id']
        amount = expense.get('total_amount', 0)
        merchant = expense.get('merchant_name', 'Unknown')
        paid_by = expense.get('paid_by', 'Unknown')

        # Get trip
        from api.utils.db_utils import get_supabase_client
        supabase = get_supabase_client()
        trip_data = supabase.table('trips').select('*').eq('id', trip_id).execute()
        if not trip_data.data:
            return {"response": "Trip not found.", "keyboard": None}

        trip = trip_data.data[0]
        participants = trip.get('participants', [])

        # Store in session
        await self.trip_service.get_or_update_session(
            user_id,
            chat_id,
            state='awaiting_expense_participants',
            context={
                'expense_id': expense_id,
                'expense_amount': amount,
                'expense_description': merchant,
                'paid_by': paid_by,
                'trip_id': trip_id,
                'participants_selected': []
            }
        )

        # Create keyboard for participant selection
        keyboard = {
            "inline_keyboard": [
                [{"text": f"☐ {p}", "callback_data": f"participant_toggle:{expense_id}:{p}"}]
                for p in participants
            ] + [
                [{"text": "Done", "callback_data": f"participants_done:{expense_id}"}]
            ]
        }

        message = f"""${amount:.2f} - {merchant}
Paid by: {paid_by}

Who is involved in this expense?
Select all who should split this expense:"""

        # Send message with keyboard
        if self.telegram_utils:
            await self.telegram_utils.send_message_with_keyboard(chat_id, message, keyboard)
            return {"response": None, "keyboard": None}
        else:
            return {"response": message, "keyboard": None}

    async def handle_cancel_edit_callback(self) -> str:
        """Handle cancelled expense edit."""
        return "Edit cancelled."

    async def handle_itinerary(self, user_id: str, chat_id: str) -> str:
        """
        Handle /itinerary command - show trip schedule.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            str: Formatted itinerary or error message
        """
        if not self.itinerary_service:
            return "Itinerary feature not available."

        # Get current trip
        trip = await self.trip_service.get_current_trip(user_id, chat_id)
        if not trip:
            return """❌ No active trip found!

Create a trip first: /new_trip <trip name>"""

        # Get itinerary items
        items = await self.itinerary_service.get_trip_itinerary(trip['id'])

        if not items:
            return f"""📅 No itinerary yet for {trip['trip_name']}!

You can paste your schedule and I'll detect it automatically, or add items manually."""

        # Format itinerary by day
        by_day = {}
        for item in items:
            day_order = item.get('day_order', 0)
            date = item.get('date', 'Unknown date')
            key = f"Day {day_order}" if day_order else date

            if key not in by_day:
                by_day[key] = []
            by_day[key].append(item)

        # Build response
        response_lines = [f"📅 Itinerary for {trip['trip_name']}:\n"]

        for day_key in sorted(by_day.keys()):
            day_items = by_day[day_key]
            response_lines.append(f"\n**{day_key}:**")

            for item in sorted(day_items, key=lambda x: (x.get('time_order', 0), x.get('time', ''))):
                time = item.get('time', '')
                title = item.get('title', 'Activity')
                location = item.get('location', '')
                description = item.get('description', '')

                time_str = f"{time} - " if time else ""
                location_str = f" ({location})" if location else ""
                desc_str = f"\n    {description}" if description else ""

                response_lines.append(f"  • {time_str}{title}{location_str}{desc_str}")

        return "\n".join(response_lines)

    async def handle_wishlist(self, user_id: str, chat_id: str) -> str:
        """
        Handle /wishlist command - show places to visit.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID

        Returns:
            str: Formatted wishlist or error message
        """
        if not self.places_service:
            return "Wishlist feature not available."

        # Get current trip
        trip = await self.trip_service.get_current_trip(user_id, chat_id)
        if not trip:
            return """❌ No active trip found!

Create a trip first: /new_trip <trip name>"""

        # Get places
        all_places = await self.places_service.get_trip_places(trip['id'])

        if not all_places:
            return f"""📍 No places in your wishlist yet for {trip['trip_name']}!

Mention places you want to visit and I'll add them automatically, or share Google Maps links."""

        # Get summary stats
        summary = await self.places_service.get_places_summary(trip['id'])

        # Group by category
        by_category = {}
        for place in all_places:
            category = place.get('category', 'other')
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(place)

        # Build response
        response_lines = [f"📍 Places Wishlist for {trip['trip_name']}:\n"]

        # Add summary
        total = summary.get('total_places', 0)
        visited = summary.get('visited_count', 0)
        avg_rating = summary.get('avg_rating')

        response_lines.append(f"Total: {total} places | Visited: {visited}")
        if avg_rating:
            response_lines.append(f"Avg Rating: ⭐ {avg_rating}")
        response_lines.append("")

        # Category order
        category_order = ['restaurant', 'attraction', 'shopping', 'nightlife', 'other']
        category_emoji = {
            'restaurant': '🍽️',
            'attraction': '🏛️',
            'shopping': '🛍️',
            'nightlife': '🍻',
            'other': '📍'
        }

        for category in category_order:
            if category in by_category:
                places = by_category[category]
                emoji = category_emoji.get(category, '📍')

                response_lines.append(f"\n**{emoji} {category.title()} ({len(places)}):**")

                for place in places[:10]:  # Limit to 10 per category
                    name = place.get('name', 'Unknown')
                    rating = place.get('rating')
                    visited = place.get('visited', False)
                    notes = place.get('notes', '')

                    rating_str = f" ⭐{rating}" if rating else ""
                    visited_str = " ✓" if visited else ""
                    notes_str = f" - {notes}" if notes else ""

                    response_lines.append(f"  • {name}{rating_str}{visited_str}{notes_str}")

        return "\n".join(response_lines)
