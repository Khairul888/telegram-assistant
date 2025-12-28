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
telegram_utils = None
command_handler = None
file_handler = None
message_handler = None


def initialize_services():
    """Initialize all services lazily on first request."""
    global _services_initialized, supabase, gemini, trip_service, expense_service
    global settlement_service, telegram_utils, command_handler, file_handler, message_handler

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

        # Initialize handlers
        command_handler = CommandHandler(trip_service, expense_service, settlement_service)
        file_handler = FileHandler(gemini, trip_service, expense_service,
                                   settlement_service, telegram_utils, supabase)
        message_handler = MessageHandler(gemini, trip_service, supabase)

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
            "version": "MVP 1.0",
            "features": ["trip management", "expense tracking", "Q&A"]
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
            elif text.startswith('/new_trip'):
                response = await command_handler.handle_new_trip(user_id, text)
            elif text.startswith('/list_trips'):
                response = await command_handler.handle_list_trips(user_id)
            elif text.startswith('/current_trip'):
                response = await command_handler.handle_current_trip(user_id)
            elif text.startswith('/balance'):
                response = await command_handler.handle_balance(user_id)
            elif text.startswith('/start'):
                response = await command_handler.handle_start()
            elif text.startswith('/help'):
                response = await command_handler.handle_help()
            else:
                # Q&A with trip context
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
            if callback_data.startswith("split_"):
                response_dict = await file_handler.handle_split_callback(
                    callback_data, user_id, chat_id
                )
            elif callback_data.startswith("paid_by:"):
                response_dict = await file_handler.handle_paid_by_callback(
                    callback_data, chat_id
                )

            # Send response if provided
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
