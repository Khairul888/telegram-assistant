"""Base agent class for all specialized agents."""


class BaseAgent:
    """Base class for all agents with function calling and streaming."""

    def __init__(self, gemini_service, services_dict, telegram_utils):
        """
        Initialize agent.

        Args:
            gemini_service: GeminiService instance
            services_dict: Dict of service instances {'trip': ..., 'expense': ...}
            telegram_utils: TelegramUtils instance
        """
        self.gemini = gemini_service
        self.services = services_dict
        self.telegram = telegram_utils
        self.tools = self._define_tools()

    def _define_tools(self) -> list:
        """
        Override in subclass to return function declarations.

        Returns:
            list: List of tool definitions for Gemini function calling
        """
        raise NotImplementedError("Subclass must implement _define_tools()")

    async def process(self, user_id: str, chat_id: str, message: str,
                     trip_context: dict) -> dict:
        """
        Main processing loop with streaming.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message: User message text
            trip_context: Current trip dict

        Returns:
            dict: {"success": bool, "response": str, "already_sent": bool}
        """
        # Send initial status
        status_msg = await self.telegram.send_message(chat_id, "Thinking...")
        status_msg_id = status_msg.get("message_id") if status_msg else None

        try:
            # Build context
            context = self._build_context(trip_context)

            # Call Gemini with tools
            result = await self.gemini.call_function(
                prompt=message,
                tools=self.tools,
                system_instruction=context
            )

            if result["type"] == "function_call":
                # Update status with action
                action_emoji = self._get_action_emoji(result["function_name"])
                if status_msg_id:
                    await self.telegram.edit_message_text(
                        chat_id, status_msg_id,
                        f"{action_emoji} Processing..."
                    )

                # Execute function
                output = await self._call_function(
                    result["function_name"],
                    result["arguments"],
                    user_id,
                    trip_context["id"]
                )

                # Delete status
                if status_msg_id:
                    await self.telegram.delete_message(chat_id, status_msg_id)

                # Format response
                response = self._format_output(result["function_name"], output)
                return {"success": True, "response": response, "already_sent": False}

            else:
                # Text response - delete status
                if status_msg_id:
                    await self.telegram.delete_message(chat_id, status_msg_id)

                return {"success": True, "response": result["text"], "already_sent": False}

        except Exception as e:
            # Delete status on error
            if status_msg_id:
                try:
                    await self.telegram.delete_message(chat_id, status_msg_id)
                except:
                    pass

            return {"success": False, "response": f"Error: {str(e)}", "already_sent": False}

    async def _call_function(self, function_name: str, args: dict,
                            user_id: str, trip_id: int) -> dict:
        """
        Override in subclass to execute function calls.

        Args:
            function_name: Name of the function to call
            args: Function arguments
            user_id: Telegram user ID
            trip_id: Trip ID

        Returns:
            dict: Function execution result
        """
        raise NotImplementedError("Subclass must implement _call_function()")

    def _build_context(self, trip_context: dict) -> str:
        """
        Build system instruction from trip context.

        Args:
            trip_context: Current trip dict

        Returns:
            str: System instruction for LLM
        """
        trip_name = trip_context.get('trip_name', 'Unknown')
        location = trip_context.get('location', 'Unknown')
        participants = trip_context.get('participants', [])

        participants_str = ', '.join(participants) if participants else 'No participants'

        return f"""You are a helpful travel assistant for trip "{trip_name}" to {location}.
Participants: {participants_str}

Use the available tools to help the user manage their trip. Do not use bold formatting or include reasoning."""

    def _format_output(self, function_name: str, output: dict) -> str:
        """
        Format function output for user.

        Args:
            function_name: Name of the function that was called
            output: Function execution result

        Returns:
            str: Formatted message for user
        """
        if not output.get("success"):
            return f"Error: {output.get('error', 'Unknown error')}"
        return "Done"

    def _get_action_emoji(self, function_name: str) -> str:
        """
        Get emoji for function action.

        Args:
            function_name: Name of the function

        Returns:
            str: Emoji representing the action
        """
        emoji_map = {
            "create_expense": "💰",
            "list_expenses": "📊",
            "get_expense_summary": "📊",
            "delete_expense": "🗑️",
            "update_expense": "✏️",
            "add_place": "📍",
            "get_places": "🗺️",
            "mark_place_visited": "✅",
            "delete_place": "🗑️",
            "get_itinerary": "📅",
            "add_itinerary_items": "📝",
            "update_itinerary_item": "✏️",
            "delete_itinerary_item": "🗑️",
            "calculate_balance": "⚖️",
            "get_settlement_summary": "💵",
            "get_current_trip": "🎫",
            "get_all_trips": "🗂️",
            "update_trip": "✏️"
        }
        return emoji_map.get(function_name, "⚙️")
