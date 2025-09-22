"""
Minimal Telegram bot for Vercel deployment.
Phase 1: Essential functionality only - job orchestration and basic AI chat.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

try:
    from supabase import create_client, Client
    import google.generativeai as genai
    from dotenv import load_dotenv
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    print(f"Import error: {e}")

# Load environment variables
load_dotenv()


class SupabaseJobQueue:
    """Simple job queue using Supabase."""

    def __init__(self):
        if DEPENDENCIES_AVAILABLE:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')

            if supabase_url and supabase_key:
                self.supabase: Client = create_client(supabase_url, supabase_key)
                self.available = True
            else:
                self.available = False
        else:
            self.available = False

    async def create_job(self, file_name: str, file_id: str, user_id: str) -> dict:
        """Create a new processing job."""
        if not self.available:
            return {"success": False, "error": "Job queue not available"}

        try:
            job_data = {
                "file_name": file_name,
                "file_id": file_id,
                "user_id": str(user_id),
                "status": "queued",
                "created_at": datetime.now().isoformat(),
            }

            result = self.supabase.table('processing_jobs').insert(job_data).execute()

            return {
                "success": True,
                "job_id": result.data[0]['id'] if result.data else None,
                "message": "Processing job created successfully"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_job_status(self, job_id: str) -> dict:
        """Get status of a processing job."""
        if not self.available:
            return {"success": False, "error": "Job queue not available"}

        try:
            result = self.supabase.table('processing_jobs').select("*").eq('id', job_id).execute()

            if result.data:
                return {"success": True, "job": result.data[0]}
            else:
                return {"success": False, "error": "Job not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}


class SimpleGeminiService:
    """Lightweight Gemini AI service."""

    def __init__(self):
        if DEPENDENCIES_AVAILABLE:
            api_key = os.getenv('GOOGLE_GEMINI_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.available = True
            else:
                self.available = False
        else:
            self.available = False

    async def generate_response(self, prompt: str, system_instruction: str = None) -> str:
        """Generate AI response."""
        if not self.available:
            return "AI service temporarily unavailable. Please try again later."

        try:
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\nUser: {prompt}"

            response = self.model.generate_content(full_prompt)
            return response.text if response.text else "I'm unable to generate a response right now."
        except Exception as e:
            return f"AI service error: {str(e)}"


# Initialize services
job_queue = SupabaseJobQueue()
gemini_service = SimpleGeminiService()


class handler(BaseHTTPRequestHandler):
    """Minimal Telegram webhook handler."""

    def do_POST(self):
        """Handle POST requests from Telegram webhook."""
        try:
            # Read the request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            # Parse JSON
            try:
                update = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            # Extract message info
            message_info = self.extract_message_info(update)

            if message_info:
                # Process message with AI and send response
                self.process_message_with_ai(message_info)

            # Send success response to Telegram
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            response = {
                "status": "ok",
                "message": "Update processed successfully"
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            # Still send 200 to Telegram to avoid retries
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                "status": "error",
                "message": f"Processing error: {str(e)}"
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def do_GET(self):
        """Handle GET requests for status."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {
            "status": "ok",
            "message": "Telegram bot webhook is operational",
            "phase": "Phase 1 - Minimal Deployment",
            "features": ["Basic AI chat", "Job queue", "File processing queue"],
            "dependencies_available": DEPENDENCIES_AVAILABLE,
            "services": {
                "gemini": gemini_service.available if 'gemini_service' in globals() else False,
                "job_queue": job_queue.available if 'job_queue' in globals() else False
            }
        }
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def extract_message_info(self, update):
        """Extract basic message information from update."""
        try:
            if "message" in update:
                message = update["message"]

                # Extract basic info
                chat_id = message["chat"]["id"]
                message_id = message["message_id"]

                # Extract user info
                user = message.get("from", {})
                user_id = user.get("id")
                first_name = user.get("first_name", "there")

                # Extract message content
                content = ""
                if "text" in message:
                    content = message["text"]
                elif "caption" in message:
                    content = message["caption"]
                elif "document" in message:
                    # File upload detected
                    doc = message["document"]
                    content = f"[Document: {doc.get('file_name', 'Unknown')}]"
                    return {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "user_id": user_id,
                        "first_name": first_name,
                        "content": content,
                        "file_info": {
                            "file_id": doc.get("file_id"),
                            "file_name": doc.get("file_name"),
                            "file_size": doc.get("file_size", 0)
                        }
                    }
                elif "photo" in message:
                    content = "[Photo]"
                else:
                    content = "[Other message type]"

                return {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "user_id": user_id,
                    "first_name": first_name,
                    "content": content
                }
        except Exception as e:
            print(f"Error extracting message info: {e}")

        return None

    def process_message_with_ai(self, message_info):
        """Process message with AI and send intelligent response."""
        try:
            # Create event loop if one doesn't exist
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Process message asynchronously
            loop.run_until_complete(self._async_process_message(message_info))

        except Exception as e:
            print(f"Error in AI message processing: {e}")
            # Fallback to simple response
            self._send_error_response(message_info, str(e))

    async def _async_process_message(self, message_info):
        """Async method to process message with AI."""
        try:
            chat_id = message_info["chat_id"]
            user_content = message_info["content"]
            first_name = message_info.get("first_name", "there")

            # Handle file uploads
            if "file_info" in message_info:
                response_text = await self._handle_file_upload(message_info)

            # Handle special commands
            elif user_content.lower().startswith('/start'):
                response_text = await self._handle_start_command(first_name)

            elif user_content.lower().startswith('/help'):
                response_text = await self._handle_help_command()

            elif user_content.lower().startswith('/status'):
                response_text = await self._handle_status_command(first_name)

            else:
                # Generate AI response for general messages
                if DEPENDENCIES_AVAILABLE and gemini_service.available:
                    response_text = await self._generate_ai_response(user_content, first_name)
                else:
                    response_text = f"Hey! Running in minimal mode right now. Upload some travel pics or receipts and I'll queue them for processing. Use /help for more info."

            # Send response
            await self._send_telegram_message(chat_id, response_text)

        except Exception as e:
            print(f"Error in async message processing: {e}")
            await self._send_telegram_message(message_info["chat_id"], f"❌ Processing error: {str(e)}")

    async def _handle_file_upload(self, message_info) -> str:
        """Handle file upload by creating processing job."""
        try:
            file_info = message_info["file_info"]
            file_name = file_info["file_name"]
            file_id = file_info["file_id"]
            user_id = message_info["user_id"]
            first_name = message_info["first_name"]

            # Create processing job
            job_result = await job_queue.create_job(file_name, file_id, user_id)

            if job_result["success"]:
                return f"""📸 Got your {file_name}!

Queued for processing. When Phase 2 is ready, I'll:
• Extract text from tickets/receipts
• Remember travel details
• Track expenses automatically

For now, it's safely stored and ready for processing!"""
            else:
                return f"❌ Couldn't queue {file_name}\nError: {job_result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"❌ **Error Processing Upload**\n\nError: {str(e)}"

    async def _handle_start_command(self, first_name: str) -> str:
        """Handle /start command."""
        return f"""✈️ Hey {first_name}!

I'm your travel buddy and expense tracker. Upload photos of:
• Flight tickets, hotel bookings, itineraries → I'll remember details for you
• Receipts → I'll break them down and track group expenses

Just send me pics and ask stuff like "when's our flight?" or "what did we spend on food?"

Phase 1: Basic setup and image queueing
Phase 2: Full OCR and expense tracking coming soon!"""

    async def _handle_help_command(self) -> str:
        """Handle /help command."""
        return """📋 Commands:

🏠 `/start` - What I do
❓ `/help` - This help
📊 `/status` - System status

**Upload pics of:**
✈️ Tickets, bookings, itineraries
🧾 Receipts, bills

**Ask me stuff like:**
• "When's our flight?"
• "What did we spend on food?"
• "Show me hotel details"

Phase 1: Just queueing your pics
Phase 2: Full OCR and expense tracking"""

    async def _handle_status_command(self, first_name: str) -> str:
        """Handle /status command."""
        try:
            status_emoji = "✅" if DEPENDENCIES_AVAILABLE else "⚠️"

            services_status = []
            if 'gemini_service' in globals():
                emoji = "✅" if gemini_service.available else "❌"
                services_status.append(f"{emoji} Gemini AI")

            if 'job_queue' in globals():
                emoji = "✅" if job_queue.available else "❌"
                services_status.append(f"{emoji} Job Queue")

            return f"""📊 **System Status Report**

{status_emoji} **Overall Status:** Phase 1 Deployed

**Services:**
{chr(10).join(services_status) if services_status else "❌ No services available"}

**Current Phase:** 1 - Minimal Deployment
**Target:** Under 250MB, fast responses
**Focus:** Job queueing and basic AI

**Architecture:**
• Vercel: Bot hosting (this service)
• Supabase: Job queue and database
• Railway: Processing (Phase 2)

👋 Hello {first_name}! System ready for file queueing!"""

        except Exception as e:
            return f"⚠️ **Status Check Failed**\n\nError: {str(e)}"

    async def _generate_ai_response(self, user_message: str, first_name: str) -> str:
        """Generate AI response for general messages."""
        try:
            system_instruction = f"""You are a casual travel companion and expense tracking assistant. The user's name is {first_name}.

You help with:
- Remembering travel details from uploaded photos (tickets, itineraries, bookings)
- Tracking group expenses from receipt photos
- Answering travel-related questions

Be casual and friendly. You're currently in Phase 1 (basic queueing), with full OCR and expense tracking coming in Phase 2."""

            ai_response = await gemini_service.generate_response(user_message, system_instruction)
            return ai_response

        except Exception as e:
            return f"Having trouble with AI right now. Try /help or /status, or just upload some travel pics!"

    async def _send_telegram_message(self, chat_id: str, text: str):
        """Send message to Telegram."""
        try:
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                print("No bot token found")
                return False

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }

            data_encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_encoded, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print(f"Message sent successfully to {chat_id}")
                    return True
                else:
                    print(f"Failed to send message: {response.status}")
                    return False

        except Exception as e:
            print(f"Error sending Telegram message: {e}")
            return False

    def _send_error_response(self, message_info, error_message: str):
        """Send a simple error response."""
        try:
            chat_id = message_info["chat_id"]
            first_name = message_info.get("first_name", "there")

            error_text = f"❌ Hi {first_name}! I encountered an error: {error_message}\n\nTry using `/help` for available commands."

            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                return False

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": error_text
            }

            data_encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_encoded, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(req) as response:
                return response.status == 200

        except Exception as e:
            print(f"Error sending error response: {e}")
            return False