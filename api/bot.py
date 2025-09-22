from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse
import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from src.core.logger import get_logger
from src.ai.gemini_service import gemini_service
from src.workflows.document_ingestion import document_ingestion_workflow

logger = get_logger(__name__)


class handler(BaseHTTPRequestHandler):

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
        """Handle GET requests for bot info."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {
            "status": "ok",
            "message": "Telegram bot webhook is operational",
            "endpoint": "/api/bot"
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
                    content = f"[Document: {message['document'].get('file_name', 'Unknown')}]"
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
            logger.error(f"Error in AI message processing: {e}")
            # Fallback to simple response
            self._send_error_response(message_info, str(e))

    async def _async_process_message(self, message_info):
        """Async method to process message with AI."""
        try:
            chat_id = message_info["chat_id"]
            user_content = message_info["content"]
            first_name = message_info.get("first_name", "there")

            logger.info(f"Processing message from {first_name}: {user_content[:100]}")

            # Handle special commands
            if user_content.lower().startswith('/start'):
                response_text = await self._handle_start_command(first_name)

            elif user_content.lower().startswith('/help'):
                response_text = await self._handle_help_command()

            elif user_content.lower().startswith('/status'):
                response_text = await self._handle_status_command(first_name)

            elif user_content.lower().startswith('/process'):
                response_text = await self._handle_process_command()

            elif user_content.lower().startswith('/search'):
                search_query = user_content[7:].strip()
                response_text = await self._handle_search_command(search_query)

            else:
                # Generate AI response for general messages
                response_text = await self._generate_ai_response(user_content, first_name)

            # Send response
            await self._send_telegram_message(chat_id, response_text)

        except Exception as e:
            logger.error(f"Error in async message processing: {e}")
            await self._send_telegram_message(message_info["chat_id"], f"❌ Processing error: {str(e)}")

    async def _handle_start_command(self, first_name: str) -> str:
        """Handle /start command."""
        return f"""🤖 **Welcome {first_name}!**

I'm your AI-powered Document Assistant! I can:

📄 **Process Documents** from Google Drive:
• Images (OCR text extraction)
• Excel/CSV files (data analysis)
• Word documents & PDFs
• Automatic processing when uploaded

🧠 **Answer Questions** about your documents
🔍 **Search** through processed content
📊 **Analyze** and provide insights

**Quick Commands:**
• `/help` - Show all commands
• `/status` - Check system health
• `/process` - Trigger manual processing
• `/search [query]` - Search documents

Just ask me anything about your documents! 🚀"""

    async def _handle_help_command(self) -> str:
        """Handle /help command."""
        return """📋 **Available Commands:**

🏠 `/start` - Welcome message and introduction
❓ `/help` - Show this help message
📊 `/status` - Check system health
🔄 `/process` - Manually trigger document processing
🔍 `/search [query]` - Search through processed documents

**Document Processing:**
• Upload files to your configured Google Drive folder
• I'll automatically process them with AI
• Ask questions about the content
• Get summaries and insights

**Examples:**
• "Summarize the latest report"
• "What are the key findings in the data?"
• "Search for information about sales"
• "/search quarterly revenue"

Ready to help with your documents! 📚"""

    async def _handle_status_command(self, first_name: str) -> str:
        """Handle /status command."""
        try:
            # Get health status from workflow
            health_status = await document_ingestion_workflow.health_check()

            status_emoji = "✅" if health_status['status'] == 'healthy' else "⚠️"

            components_status = []
            for component, status in health_status.get('components', {}).items():
                emoji = "✅" if status == 'healthy' else "❌"
                components_status.append(f"{emoji} {component.replace('_', ' ').title()}")

            return f"""📊 **System Status Report**

{status_emoji} **Overall Status:** {health_status['status'].title()}

**Components:**
{chr(10).join(components_status)}

📈 **Stats:**
• Processed Files: {health_status.get('processed_files_count', 0)}
• Monitoring Active: {"Yes" if health_status.get('is_monitoring') else "No"}

👋 Hello {first_name}! System is ready for document processing!"""

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return f"⚠️ **Status Check Failed**\n\nError: {str(e)}"

    async def _handle_process_command(self) -> str:
        """Handle /process command to manually trigger processing."""
        try:
            logger.info("Manual processing triggered via /process command")

            # Trigger processing of new files
            result = await document_ingestion_workflow.process_new_files(since_minutes=60)

            if result['files_found'] == 0:
                return "🔍 **No New Files Found**\n\nNo files to process in the last hour. Upload files to your Google Drive folder and try again!"

            success_count = result['files_processed']
            error_count = result['files_failed']

            if success_count > 0 and error_count == 0:
                return f"✅ **Processing Complete!**\n\n📄 Successfully processed {success_count} file(s)\n\nYou can now ask questions about these documents!"

            elif success_count > 0 and error_count > 0:
                return f"⚠️ **Processing Partially Complete**\n\n✅ Processed: {success_count} file(s)\n❌ Failed: {error_count} file(s)\n\nCheck logs for error details."

            else:
                return f"❌ **Processing Failed**\n\n{error_count} file(s) failed to process. Please check your file formats and try again."

        except Exception as e:
            logger.error(f"Error in manual processing: {e}")
            return f"❌ **Processing Error**\n\nError: {str(e)}"

    async def _handle_search_command(self, search_query: str) -> str:
        """Handle /search command."""
        if not search_query:
            return "🔍 **Search Usage:**\n\n`/search [your query]`\n\nExample: `/search quarterly revenue`"

        # Placeholder for document search
        # In production, this would search through the vector database
        return f"""🔍 **Search Results for:** "{search_query}"

⚠️ **Search functionality is being prepared**

Your query has been noted. Once document vector storage is fully implemented, I'll be able to search through:

• All processed documents
• Image text content
• Spreadsheet data
• Document summaries

For now, try asking me general questions about documents you've uploaded recently!"""

    async def _generate_ai_response(self, user_message: str, first_name: str) -> str:
        """Generate AI response for general messages."""
        try:
            # Create context-aware prompt
            system_instruction = f"""You are an AI Document Assistant named Claude. You help users with document processing, analysis, and queries.

The user's name is {first_name}. You have access to:
- Google Drive document processing
- OCR for images
- Excel/CSV analysis
- Word document and PDF processing
- AI-powered insights

Be helpful, concise, and mention relevant document processing capabilities when appropriate."""

            # Generate response using Gemini
            ai_response = await gemini_service.generate_response(
                prompt=user_message,
                system_instruction=system_instruction,
                temperature=0.7
            )

            return f"🤖 {ai_response}"

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return f"🤖 Hi {first_name}! I'm having trouble generating a response right now. Try asking about document processing or use one of my commands like `/help` or `/status`!"

    async def _send_telegram_message(self, chat_id: str, text: str):
        """Send message to Telegram using async approach."""
        try:
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                logger.error("No bot token found")
                return False

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }

            # Encode data
            data_encoded = urllib.parse.urlencode(data).encode('utf-8')

            # Create request
            req = urllib.request.Request(url, data=data_encoded, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            # Send request
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    logger.info(f"Message sent successfully to {chat_id}")
                    return True
                else:
                    logger.error(f"Failed to send message: {response.status}")
                    return False

        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
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
            logger.error(f"Error sending error response: {e}")
            return False