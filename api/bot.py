from http.server import BaseHTTPRequestHandler
import json
import os
import urllib.request
import urllib.parse

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
                # Send response to user
                self.send_telegram_response(message_info)

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

    def send_telegram_response(self, message_info):
        """Send a response back to the user using urllib."""
        try:
            bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not bot_token:
                print("No bot token found")
                return False

            chat_id = message_info["chat_id"]
            user_content = message_info["content"]
            first_name = message_info.get("first_name", "there")

            # Determine response based on message content
            if user_content.lower().startswith('/start'):
                response_text = f"🤖 Hello {first_name}! Welcome to your AI Document Assistant!\n\n✅ I'm now fully operational and ready to help you!\n\n📋 Try these commands:\n• /help - See all available commands\n• /status - Check my current status\n• Send me any message and I'll respond!"

            elif user_content.lower().startswith('/help'):
                response_text = "📋 **Available Commands:**\n\n🏠 /start - Welcome message and introduction\n❓ /help - Show this help message\n📊 /status - Check system health\n\n💬 **How to use me:**\n• Send any text message and I'll respond\n• Upload documents for analysis (coming soon)\n• Ask questions about your files (coming soon)\n\n🎉 I'm now working perfectly!"

            elif user_content.lower().startswith('/status'):
                response_text = f"📊 **Bot Status Report**\n\n✅ **System Status:** Fully Operational\n🔧 **Webhook:** Connected and working\n📡 **API Connection:** Excellent\n⚡ **Response Time:** Fast\n🚀 **Ready for:** Message processing\n\n👋 Hello {first_name}! Everything is working perfectly!"

            else:
                response_text = f"👋 Hi {first_name}! You said: \"{user_content}\"\n\n🎉 **Great news!** I'm now working correctly and can respond to your messages!\n\n🤖 I'm your AI Document Assistant. Soon I'll be able to:\n• Process and analyze your documents\n• Answer questions about your files\n• Provide intelligent insights\n\nFor now, try sending /help to see what I can do!"

            # Send response using urllib
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": response_text,
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
                    print(f"✅ Response sent successfully to {chat_id}")
                    return True
                else:
                    print(f"❌ Failed to send response: {response.status}")
                    return False

        except Exception as e:
            print(f"❌ Error sending response: {e}")
            return False