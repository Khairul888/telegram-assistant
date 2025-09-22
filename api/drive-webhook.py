"""
Minimal Google Drive webhook for Vercel deployment.
Phase 1: Basic webhook receiving and job queue integration.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    print(f"Import error: {e}")

# Load environment variables
load_dotenv()


class MinimalDriveWebhook:
    """Minimal Google Drive webhook handler."""

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

    async def log_webhook_event(self, event_data: dict) -> dict:
        """Log webhook event for processing in Phase 2."""
        if not self.available:
            return {"success": False, "error": "Database not available"}

        try:
            # Log the webhook event for Phase 2 processing
            log_data = {
                "event_type": "drive_webhook",
                "event_data": event_data,
                "status": "received",
                "created_at": datetime.now().isoformat(),
            }

            # Store in a webhook_logs table for Phase 2 to process
            result = self.supabase.table('webhook_logs').insert(log_data).execute()

            return {
                "success": True,
                "log_id": result.data[0]['id'] if result.data else None,
                "message": "Webhook event logged successfully"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# Initialize webhook handler
drive_webhook = MinimalDriveWebhook()


class handler(BaseHTTPRequestHandler):
    """Minimal Google Drive webhook handler for Vercel."""

    def do_POST(self):
        """Handle POST requests from Google Drive push notifications."""
        try:
            # Read the request body
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)

            # Get headers
            channel_id = self.headers.get('X-Goog-Channel-ID')
            resource_id = self.headers.get('X-Goog-Resource-ID')
            resource_state = self.headers.get('X-Goog-Resource-State')
            resource_uri = self.headers.get('X-Goog-Resource-URI')
            changed = self.headers.get('X-Goog-Changed')

            print(f"Drive webhook received: state={resource_state}, channel={channel_id}")

            # Parse request body if present
            notification_data = {}
            if content_length > 0:
                try:
                    notification_data = json.loads(post_data.decode('utf-8'))
                except json.JSONDecodeError:
                    print("Could not parse webhook body as JSON")

            # Log the webhook event for Phase 2 processing
            event_data = {
                "channel_id": channel_id,
                "resource_id": resource_id,
                "resource_state": resource_state,
                "resource_uri": resource_uri,
                "changed": changed,
                "notification_data": notification_data,
                "timestamp": datetime.now().isoformat()
            }

            # For Phase 1, we just log the event
            # Phase 2 will add actual processing
            if DEPENDENCIES_AVAILABLE and drive_webhook.available:
                # Try to create event loop for async operation
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                log_result = loop.run_until_complete(drive_webhook.log_webhook_event(event_data))
                response_data = {
                    "status": "logged",
                    "message": "Webhook event logged for Phase 2 processing",
                    "phase": "Phase 1 - Logging Only",
                    "log_result": log_result,
                    "resource_state": resource_state
                }
            else:
                response_data = {
                    "status": "received",
                    "message": "Webhook received but logging unavailable",
                    "phase": "Phase 1 - Minimal Mode",
                    "resource_state": resource_state
                }

            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            print(f"Error processing Drive webhook: {e}")

            # Still send 200 to prevent retries
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                "status": "error",
                "message": f"Webhook processing error: {str(e)}",
                "phase": "Phase 1 - Error Handling"
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def do_GET(self):
        """Handle GET requests for webhook verification and status."""
        try:
            # Check if this is a webhook verification request
            verification_token = self.headers.get('X-Goog-Channel-Token')

            if verification_token:
                # This is likely a verification request from Google
                print(f"Drive webhook verification request with token: {verification_token}")

                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK')
                return

            # Regular status check
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            status_response = {
                "status": "ok",
                "message": "Google Drive webhook endpoint is operational",
                "phase": "Phase 1 - Minimal Deployment",
                "features": ["Webhook logging", "Event queuing", "Phase 2 preparation"],
                "endpoint": "/api/drive-webhook",
                "dependencies_available": DEPENDENCIES_AVAILABLE,
                "services": {
                    "supabase": drive_webhook.available if 'drive_webhook' in globals() else False
                }
            }
            self.wfile.write(json.dumps(status_response).encode('utf-8'))

        except Exception as e:
            print(f"Error handling Drive webhook GET request: {e}")

            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                "status": "error",
                "message": str(e),
                "phase": "Phase 1 - Error State"
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def log_message(self, format, *args):
        """Override to use print instead of stderr."""
        print(f"Drive webhook: {format % args}")


# Phase 1 Note:
# This webhook currently only logs events for Phase 2 processing.
# To set up actual Google Drive push notifications, you'll need to:
# 1. Enable Google Drive API in Google Cloud Console
# 2. Set up a push notification channel
# 3. Configure the webhook URL to point to this endpoint
#
# This will be implemented in Phase 2 with the Railway processing service.