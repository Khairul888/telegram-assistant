from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        """Handle POST requests from Telegram webhook."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {"status": "ok", "message": "Webhook received POST"}
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def do_GET(self):
        """Handle GET requests for webhook info."""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

        response = {"status": "ok", "message": "Simple webhook is working!"}
        self.wfile.write(json.dumps(response).encode('utf-8'))