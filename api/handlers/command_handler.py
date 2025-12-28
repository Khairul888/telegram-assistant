"""Command handler for bot commands."""
from typing import Dict


class CommandHandler:
    """Handles bot commands and multi-step conversation flows."""

    def __init__(self, trip_service, expense_service, settlement_service):
        """
        Initialize with service dependencies.

        Args:
            trip_service: TripService instance
            expense_service: ExpenseService instance
            settlement_service: SettlementService instance
        """
        self.trip_service = trip_service
        self.expense_service = expense_service
        self.settlement_service = settlement_service

    async def handle_new_trip(self, user_id: str, message_text: str) -> str:
        """
        Handle /new_trip command - start trip creation flow.

        Args:
            user_id: Telegram user ID
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
            state='awaiting_location',
            context={'trip_name': trip_name}
        )

        return f"""Great! Creating trip: "{trip_name}"

Where are you traveling to? (e.g., "Tokyo, Japan")"""

    async def handle_location_response(self, user_id: str, location: str) -> str:
        """
        Handle location response during trip creation.

        Args:
            user_id: Telegram user ID
            location: Location text

        Returns:
            str: Response message
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id)
        context = session.get('conversation_context', {})
        trip_name = context.get('trip_name')

        if not trip_name:
            return "Error: Trip creation session expired. Please start over with /new_trip"

        # Update context and change state
        context['location'] = location
        await self.trip_service.get_or_update_session(
            user_id,
            state='awaiting_participants',
            context=context
        )

        return f"""Location set: {location}

Who's on this trip? Send names separated by commas.
Example: Alice, Bob, Carol

(Include yourself if you want to track your expenses too!)"""

    async def handle_participants_response(self, user_id: str, participants_text: str) -> str:
        """
        Handle participants response and create trip.

        Args:
            user_id: Telegram user ID
            participants_text: Comma-separated participant names

        Returns:
            str: Response message
        """
        # Get session context
        session = await self.trip_service.get_or_update_session(user_id)
        context = session.get('conversation_context', {})
        trip_name = context.get('trip_name')
        location = context.get('location')

        if not trip_name or not location:
            return "Error: Trip creation session expired. Please start over with /new_trip"

        # Parse participants
        participants = [p.strip() for p in participants_text.split(',') if p.strip()]

        if not participants:
            return "Please provide at least one participant name."

        # Create trip
        result = await self.trip_service.create_trip(
            user_id, trip_name, location, participants
        )

        if result.get('success'):
            # Clear conversation state
            await self.trip_service.clear_conversation_state(user_id)

            participants_list = '\n'.join([f"  • {p}" for p in participants])

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

    async def handle_list_trips(self, user_id: str) -> str:
        """
        Handle /list_trips command.

        Args:
            user_id: Telegram user ID

        Returns:
            str: Response message with trip list
        """
        trips = await self.trip_service.list_trips(user_id)

        if not trips:
            return """You don't have any trips yet!

Create one with: /new_trip <trip name>

Example: /new_trip Paris 2025"""

        current_trip = await self.trip_service.get_current_trip(user_id)
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

    async def handle_current_trip(self, user_id: str) -> str:
        """
        Handle /current_trip command.

        Args:
            user_id: Telegram user ID

        Returns:
            str: Response message with current trip details
        """
        trip = await self.trip_service.get_current_trip(user_id)

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

    async def handle_balance(self, user_id: str) -> str:
        """
        Handle /balance command - show running balance.

        Args:
            user_id: Telegram user ID

        Returns:
            str: Response message with settlement details
        """
        trip = await self.trip_service.get_current_trip(user_id)

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

    async def handle_help(self) -> str:
        """Handle /help command."""
        return """📚 Commands Guide:

TRIPS:
• /new_trip <name> - Create new trip
  Example: /new_trip Tokyo 2025
• /list_trips - View all trips
• /current_trip - Show active trip details

EXPENSES:
• Upload receipt photo → I'll extract details & ask how to split
• /balance - See running balance and settlements

TRAVEL INFO:
• Upload flight ticket → I'll remember details
• Upload hotel booking → I'll save check-in dates
• Ask: "when's my flight?" or "where are we staying?"

OTHER:
• /start - Welcome message
• /help - This guide

Tips:
  - Latest trip is automatically active
  - All uploads are linked to current trip
  - Use simple names for participants (no Telegram accounts needed)"""
