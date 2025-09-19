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
                "message": "Update processed successfully",
                "update_id": update.get("update_id")
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            self.send_error(500, f"Processing error: {str(e)}")

    def do_GET(self):
        """Handle GET requests for webhook info."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {
            "status": "ok",
            "message": "Telegram webhook endpoint is operational",
            "endpoint": "/api/webhook"
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
                first_name = user.get("first_name", "")

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
                return

            chat_id = message_info["chat_id"]
            user_content = message_info["content"]
            first_name = message_info.get("first_name", "there")

            # Determine response
            if user_content.lower().startswith('/start'):
                response_text = f"🤖 Hello {first_name}! I'm your AI Document Assistant.\\n\\nI'm now working! Try sending me any text and I'll respond with proper processing."
            elif user_content.lower().startswith('/help'):
                response_text = "📋 Available commands:\\n/start - Get started\\n/help - Show this help\\n/status - Check status\\n\\nYou can also send me any message and I'll respond!"
            elif user_content.lower().startswith('/status'):
                response_text = "✅ Bot is online and working perfectly!\\n🔧 Status: Operational\\n📡 Connection: Excellent\\n🚀 Ready to process your documents!"
            else:
                response_text = f"📩 Hi {first_name}! I received your message: \\"{user_content}\\"\\n\\n🎉 Great news! The bot is now working correctly! I can process your messages and will soon have full AI document processing capabilities."

            # Send response using urllib
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": response_text
            }

            # Encode data
            data_encoded = urllib.parse.urlencode(data).encode('utf-8')

            # Create request
            req = urllib.request.Request(url, data=data_encoded, method='POST')
            req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            # Send request
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print(f"Response sent successfully to {chat_id}")
                else:
                    print(f"Failed to send response: {response.status}")

        except Exception as e:
            print(f"Error sending response: {e}")