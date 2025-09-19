from http.server import BaseHTTPRequestHandler
import json
import os

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        """Debug endpoint to check environment and configuration."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        # Check environment variables
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        gemini_key = os.getenv('GOOGLE_GEMINI_API_KEY')

        debug_info = {
            "status": "debug_info",
            "environment_variables": {
                "TELEGRAM_BOT_TOKEN": "SET" if bot_token else "MISSING",
                "TELEGRAM_BOT_TOKEN_LENGTH": len(bot_token) if bot_token else 0,
                "TELEGRAM_CHAT_ID": "SET" if chat_id else "MISSING",
                "GOOGLE_GEMINI_API_KEY": "SET" if gemini_key else "MISSING"
            },
            "environment": os.getenv('ENVIRONMENT', 'unknown'),
            "python_version": f"{os.sys.version_info.major}.{os.sys.version_info.minor}",
            "working_directory": os.getcwd()
        }

        self.wfile.write(json.dumps(debug_info, indent=2).encode('utf-8'))

    def do_POST(self):
        """Debug POST to see what Telegram is sending."""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            # Parse the JSON
            try:
                update = json.loads(post_data.decode('utf-8'))
            except:
                update = {"error": "Could not parse JSON", "raw_data": post_data.decode('utf-8')}

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            debug_response = {
                "status": "debug_post_received",
                "headers": dict(self.headers),
                "content_length": content_length,
                "telegram_update": update,
                "environment_check": {
                    "bot_token_available": bool(os.getenv('TELEGRAM_BOT_TOKEN'))
                }
            }

            self.wfile.write(json.dumps(debug_response, indent=2).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                "status": "debug_error",
                "error": str(e),
                "error_type": type(e).__name__
            }

            self.wfile.write(json.dumps(error_response).encode('utf-8'))