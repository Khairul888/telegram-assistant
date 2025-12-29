"""
Telegram Travel Assistant MVP - Main Bot Webhook Handler
Simplified serverless webhook handler for Vercel.
"""
from http.server import BaseHTTPRequestHandler
import json
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import services
from api.services.gemini_service import GeminiService
from api.services.trip_service import TripService
from api.services.expense_service import ExpenseService
from api.services.settlement_service import SettlementService

# Import handlers
from api.handlers.command_handler import CommandHandler
from api.handlers.file_handler import FileHandler
from api.handlers.message_handler import MessageHandler

# Import utilities
from api.utils.telegram_utils import TelegramUtils
from api.utils.db_utils import get_supabase_client

# Global service instances (initialized lazily)
_services_initialized = False
supabase = None
gemini = None
trip_service = None
expense_service = None
settlement_service = None
itinerary_service = None
places_service = None
telegram_utils = None
command_handler = None
file_handler = None
message_handler = None
intent_handler = None
router = None
agents_enabled = False


def initialize_services():
    """Initialize all services lazily on first request."""
    global _services_initialized, supabase, gemini, trip_service, expense_service
    global settlement_service, itinerary_service, places_service, telegram_utils
    global command_handler, file_handler, message_handler, intent_handler
    global router, agents_enabled

    if _services_initialized:
        return

    try:
        # Initialize database and utilities
        supabase = get_supabase_client()
        telegram_utils = TelegramUtils()

        # Initialize AI service
        gemini = GeminiService()

        # Initialize core services
        trip_service = TripService(supabase)
        expense_service = ExpenseService(supabase)
        settlement_service = SettlementService(expense_service)

        # Initialize new services for itinerary and places
        from api.services.itinerary_service import ItineraryService
        from api.services.places_service import PlacesService
        itinerary_service = ItineraryService(supabase)
        places_service = PlacesService(supabase)

        # Initialize handlers
        command_handler = CommandHandler(trip_service, expense_service, settlement_service,
                                        telegram_utils, itinerary_service, places_service)
        file_handler = FileHandler(gemini, trip_service, expense_service,
                                   settlement_service, telegram_utils, supabase)
        message_handler = MessageHandler(gemini, trip_service, supabase)

        # Initialize intent handler for conversational detection
        from api.handlers.intent_handler import IntentHandler
        intent_handler = IntentHandler(gemini, itinerary_service, places_service,
                                      trip_service, telegram_utils)

        # Initialize agents (feature-flag controlled)
        agents_enabled = os.getenv('USE_AGENTIC_ROUTING', 'false').lower() == 'true'

        if agents_enabled:
            from api.agents.expense_agent import ExpenseAgent
            from api.agents.router import KeywordRouter
            from api.agents.orchestrator import OrchestratorAgent

            services_dict = {
                'trip': trip_service,
                'expense': expense_service,
                'settlement': settlement_service,
                'itinerary': itinerary_service,
                'places': places_service
            }

            # Initialize just ExpenseAgent for Phase 3 PoC
            expense_agent = ExpenseAgent(gemini, services_dict, telegram_utils)

            # Placeholder for other agents (Phase 4)
            agents = {
                'expense': expense_agent
                # Other agents will be added in Phase 4
            }

            orchestrator = OrchestratorAgent(gemini, services_dict, telegram_utils)
            router = KeywordRouter(agents, orchestrator)

            print("Agents initialized (ExpenseAgent only)")

        _services_initialized = True
        print("Services initialized successfully")
    except Exception as e:
        print(f"Error initializing services: {e}")
        raise


class handler(BaseHTTPRequestHandler):
    """Vercel serverless webhook handler."""

    def do_GET(self):
        """Health check endpoint."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {
            "status": "ok",
            "version": "MVP 1.1",
            "features": ["trip management", "expense tracking", "Q&A", "enhanced splits"]
        }
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        """Handle Telegram webhook POST requests."""
        try:
            # Initialize services if needed
            initialize_services()

            # Parse request
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            update = json.loads(post_data.decode('utf-8'))

            # Process update (sync wrapper for async code)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.process_update(update))

            # Send OK to Telegram
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())

        except Exception as e:
            print(f"Error in webhook handler: {e}")
            self.send_response(200)  # Always return 200 to Telegram
            self.end_headers()

    async def process_update(self, update: dict):
        """
        Process Telegram update.

        Args:
            update: Telegram update dictionary
        """
        try:
            # Handle callback queries (inline keyboard responses)
            if "callback_query" in update:
                await self.handle_callback_query(update["callback_query"])
                return

            # Handle messages
            if "message" not in update:
                return

            message = update["message"]
            chat_id = str(message["chat"]["id"])
            user_id = str(message["from"]["id"])

            # Security check - only allow authorized chat
            authorized_chat_id = os.getenv('TELEGRAM_CHAT_ID', '1316304260')
            if chat_id != authorized_chat_id:
                print(f"Unauthorized chat ID: {chat_id}")
                return

            # Get session to check conversation state
            session = await trip_service.get_or_update_session(user_id)
            state = session.get('conversation_state')

            # Handle file uploads
            if "photo" in message or "document" in message:
                result = await file_handler.handle_file_upload(message, user_id, chat_id)
                if result.get("response"):
                    await telegram_utils.send_message(chat_id, result["response"])
                return

            # Handle text messages
            text = message.get("text", "")

            # Route based on conversation state or command
            response = None

            if state == 'awaiting_location':
                response = await command_handler.handle_location_response(user_id, text)
            elif state == 'awaiting_participants':
                response = await command_handler.handle_participants_response(user_id, text)
            elif state == 'awaiting_custom_split':
                response = await command_handler.handle_custom_split_text(user_id, chat_id, text)
            elif state == 'awaiting_edit_amount':
                response = await command_handler.handle_edit_amount_text(user_id, text)
            elif state == 'awaiting_edit_description':
                response = await command_handler.handle_edit_description_text(user_id, text)
            elif state == 'awaiting_itinerary_confirmation':
                # Handled via callback, ignore text
                response = "Please use the buttons above to confirm or cancel."
            elif state == 'awaiting_place_category':
                # Handled via callback, ignore text
                response = "Please select a category using the buttons above."
            elif text.startswith('/new_trip'):
                response = await command_handler.handle_new_trip(user_id, text)
            elif text.startswith('/add_expense'):
                result = await command_handler.handle_add_expense(user_id, chat_id, text)
                if result.get("response"):
                    await telegram_utils.send_message(chat_id, result["response"])
                # If keyboard was sent, message already sent in handler
                return
            elif text.startswith('/list_trips'):
                response = await command_handler.handle_list_trips(user_id)
            elif text.startswith('/current_trip'):
                response = await command_handler.handle_current_trip(user_id)
            elif text.startswith('/balance'):
                response = await command_handler.handle_balance(user_id)
            elif text.startswith('/list_expenses'):
                result = await command_handler.handle_list_expenses(user_id, chat_id)
                if result.get("response"):
                    await telegram_utils.send_message(chat_id, result["response"])
                return
            elif text.startswith('/start'):
                response = await command_handler.handle_start()
            elif text.startswith('/help'):
                response = await command_handler.handle_help()
            elif text.startswith('/itinerary'):
                response = await command_handler.handle_itinerary(user_id)
            elif text.startswith('/wishlist'):
                response = await command_handler.handle_wishlist(user_id)
            else:
                # Conversational handling (only if no active state)
                if not state:
                    trip = await trip_service.get_current_trip(user_id)
                    if trip:
                        # NEW: Agent-based routing (feature-flag controlled)
                        if agents_enabled and router:
                            result = await router.route(user_id, chat_id, text, trip)
                            if result.get("success"):
                                response = result.get("response")
                                # Check if already sent via streaming
                                if response and not result.get("already_sent"):
                                    await telegram_utils.send_message(chat_id, response)
                                return  # Exit early, message handled

                        # OLD: Keep original intent classification (backward compatibility)
                        else:
                            intent = await gemini.classify_message_intent(text)

                            if intent == "google_maps_url":
                                result = await intent_handler.handle_google_maps_url(
                                    user_id, chat_id, text, trip
                                )
                                if result.get("handled"):
                                    response = result.get("response")
                            elif intent == "itinerary_paste":
                                result = await intent_handler.handle_itinerary_detection(
                                    user_id, chat_id, text, trip
                                )
                                if result.get("handled"):
                                    return
                            elif intent == "place_mention":
                                result = await intent_handler.handle_place_detection(
                                    user_id, chat_id, text, trip
                                )
                                if result.get("handled"):
                                    return

                # Fallback to Q&A if no intent matched or no trip
                if not response:
                    response = await message_handler.handle_question(user_id, text)

            if response:
                await telegram_utils.send_message(chat_id, response)

        except Exception as e:
            print(f"Error processing update: {e}")
            # Try to send error message to user
            try:
                if "message" in update:
                    chat_id = str(update["message"]["chat"]["id"])
                    await telegram_utils.send_message(
                        chat_id,
                        f"Sorry, I encountered an error processing your request: {str(e)}"
                    )
            except:
                pass

    async def handle_callback_query(self, callback_query: dict):
        """
        Handle inline keyboard button presses.

        Args:
            callback_query: Callback query dictionary
        """
        try:
            callback_data = callback_query["data"]
            chat_id = str(callback_query["message"]["chat"]["id"])
            user_id = str(callback_query["from"]["id"])
            callback_query_id = callback_query["id"]

            response_dict = None

            # Route based on callback data prefix
            if callback_data.startswith("receipt_paid_by:"):
                # Receipt expense - extract expense_id and payer
                parts = callback_data.split(":", 2)
                if len(parts) == 3:
                    expense_id = int(parts[1])
                    paid_by = parts[2]
                    response_dict = await file_handler.handle_receipt_paid_by_callback(
                        user_id, chat_id, expense_id, paid_by
                    )
            elif callback_data.startswith("expense_paid_by:"):
                # Manual expense - extract payer name
                paid_by = callback_data.replace("expense_paid_by:", "")
                response_dict = await command_handler.handle_expense_payer_callback(
                    user_id, chat_id, paid_by
                )
            elif callback_data.startswith("participant_toggle:"):
                # Participant multi-select toggle
                parts = callback_data.split(":", 2)
                if len(parts) == 3:
                    expense_id = int(parts[1])
                    participant = parts[2]
                    message_id = callback_query["message"]["message_id"]
                    response_dict = await command_handler.handle_participant_toggle_callback(
                        user_id, chat_id, message_id, expense_id, participant
                    )
            elif callback_data.startswith("participants_done:"):
                # Participant selection complete
                expense_id = int(callback_data.split(":")[1])
                response_dict = await command_handler.handle_participants_done_callback(
                    user_id, chat_id, expense_id
                )
            elif callback_data.startswith("split_type:"):
                # Split type selection
                parts = callback_data.split(":", 2)
                if len(parts) == 3:
                    expense_id = int(parts[1]) if parts[1] != 'None' else None
                    split_type = parts[2]
                    response_dict = await command_handler.handle_split_type_callback(
                        user_id, chat_id, expense_id, split_type
                    )
            elif callback_data.startswith("delete_expense:"):
                # Delete expense request
                expense_id = int(callback_data.split(":")[1])
                response_dict = await command_handler.handle_delete_expense_callback(
                    user_id, chat_id, expense_id
                )
            elif callback_data.startswith("confirm_delete:"):
                # Confirm delete expense
                expense_id = int(callback_data.split(":")[1])
                response = await command_handler.handle_confirm_delete_callback(
                    user_id, expense_id
                )
                if response:
                    await telegram_utils.send_message(chat_id, response)
            elif callback_data.startswith("cancel_delete:"):
                # Cancel delete
                response = await command_handler.handle_cancel_delete_callback()
                if response:
                    await telegram_utils.send_message(chat_id, response)
            elif callback_data.startswith("edit_expense:"):
                # Edit expense request - show edit menu
                expense_id = int(callback_data.split(":")[1])
                response_dict = await command_handler.handle_edit_expense_callback(
                    user_id, chat_id, expense_id
                )
            elif callback_data.startswith("edit_amount:"):
                # Edit amount request
                expense_id = int(callback_data.split(":")[1])
                response = await command_handler.handle_edit_amount_callback(
                    user_id, chat_id, expense_id
                )
                if response:
                    await telegram_utils.send_message(chat_id, response)
            elif callback_data.startswith("edit_description:"):
                # Edit description request
                expense_id = int(callback_data.split(":")[1])
                response = await command_handler.handle_edit_description_callback(
                    user_id, chat_id, expense_id
                )
                if response:
                    await telegram_utils.send_message(chat_id, response)
            elif callback_data.startswith("edit_payer_select:"):
                # Edit payer selection
                parts = callback_data.split(":", 2)
                if len(parts) == 3:
                    expense_id = int(parts[1])
                    new_payer = parts[2]
                    response = await command_handler.handle_edit_payer_select_callback(
                        user_id, expense_id, new_payer
                    )
                    if response:
                        await telegram_utils.send_message(chat_id, response)
            elif callback_data.startswith("edit_payer:"):
                # Edit payer request
                expense_id = int(callback_data.split(":")[1])
                response_dict = await command_handler.handle_edit_payer_callback(
                    user_id, chat_id, expense_id
                )
            elif callback_data.startswith("edit_split:"):
                # Edit split request
                expense_id = int(callback_data.split(":")[1])
                response_dict = await command_handler.handle_edit_split_callback(
                    user_id, chat_id, expense_id
                )
            elif callback_data.startswith("cancel_edit:"):
                # Cancel edit
                response = await command_handler.handle_cancel_edit_callback()
                if response:
                    await telegram_utils.send_message(chat_id, response)
            elif callback_data.startswith("itinerary_confirm:"):
                # Itinerary confirmation
                confirmed = callback_data.split(":")[1] == "yes"
                response = await intent_handler.handle_itinerary_confirmation(
                    user_id, chat_id, confirmed
                )
                if response:
                    await telegram_utils.send_message(chat_id, response)
            elif callback_data.startswith("place_category:"):
                # Place category selection
                category = callback_data.split(":")[1]
                response = await intent_handler.handle_place_category_selection(
                    user_id, chat_id, category
                )
                if response:
                    await telegram_utils.send_message(chat_id, response)

            # Send response if provided (for dict responses)
            if response_dict and response_dict.get("response"):
                await telegram_utils.send_message(chat_id, response_dict["response"])

            # Answer callback query to remove loading state
            await telegram_utils.answer_callback_query(callback_query_id)

        except Exception as e:
            print(f"Error handling callback query: {e}")
            # Try to answer callback query even on error
            try:
                await telegram_utils.answer_callback_query(
                    callback_query["id"],
                    f"Error: {str(e)}"
                )
            except:
                pass
