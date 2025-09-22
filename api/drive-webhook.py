"""
Google Drive webhook handler for real-time file processing.
Receives push notifications from Google Drive when files are added/modified.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from src.core.logger import get_logger
from src.workflows.document_ingestion import document_ingestion_workflow

logger = get_logger(__name__)


class handler(BaseHTTPRequestHandler):
    """Handler for Google Drive push notifications."""

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

            logger.info(f"Drive webhook received: state={resource_state}, channel={channel_id}")

            # Parse request body if present
            notification_data = {}
            if content_length > 0:
                try:
                    notification_data = json.loads(post_data.decode('utf-8'))
                except json.JSONDecodeError:
                    logger.warning("Could not parse webhook body as JSON")

            # Process the notification
            response_data = self._process_drive_notification(
                channel_id=channel_id,
                resource_id=resource_id,
                resource_state=resource_state,
                resource_uri=resource_uri,
                changed=changed,
                notification_data=notification_data
            )

            # Send success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            self.wfile.write(json.dumps(response_data).encode('utf-8'))

        except Exception as e:
            logger.error(f"Error processing Drive webhook: {e}")

            # Still send 200 to prevent retries
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                "status": "error",
                "message": f"Webhook processing error: {str(e)}"
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def do_GET(self):
        """Handle GET requests for webhook verification and status."""
        try:
            # Check if this is a webhook verification request
            verification_token = self.headers.get('X-Goog-Channel-Token')

            if verification_token:
                # This is likely a verification request from Google
                logger.info(f"Drive webhook verification request with token: {verification_token}")

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
                "endpoint": "/api/drive-webhook"
            }
            self.wfile.write(json.dumps(status_response).encode('utf-8'))

        except Exception as e:
            logger.error(f"Error handling Drive webhook GET request: {e}")

            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            error_response = {
                "status": "error",
                "message": str(e)
            }
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def _process_drive_notification(
        self,
        channel_id: str,
        resource_id: str,
        resource_state: str,
        resource_uri: str,
        changed: str,
        notification_data: dict
    ) -> dict:
        """
        Process Google Drive push notification.

        Args:
            channel_id: Notification channel ID
            resource_id: Resource that changed
            resource_state: Type of change (add, update, remove, sync)
            resource_uri: URI of the changed resource
            changed: What changed (usually "changes")
            notification_data: Additional notification data

        Returns:
            Response data dictionary
        """
        try:
            logger.info(f"Processing Drive notification: {resource_state} for {resource_id}")

            # Only process certain states
            if resource_state not in ['add', 'update']:
                logger.info(f"Ignoring resource state: {resource_state}")
                return {
                    "status": "ignored",
                    "reason": f"Resource state '{resource_state}' not processed",
                    "resource_state": resource_state
                }

            # Trigger file processing in background
            # Note: In a serverless environment, we need to process immediately
            # rather than scheduling background tasks
            result = self._trigger_file_processing()

            return {
                "status": "processed",
                "resource_state": resource_state,
                "channel_id": channel_id,
                "processing_triggered": result,
                "timestamp": self._get_current_timestamp()
            }

        except Exception as e:
            logger.error(f"Error processing Drive notification: {e}")
            return {
                "status": "error",
                "error": str(e),
                "resource_state": resource_state
            }

    def _trigger_file_processing(self) -> bool:
        """
        Trigger file processing for new/updated files.

        Returns:
            True if processing was triggered successfully
        """
        try:
            # Since we're in a serverless environment, we need to process synchronously
            # In a persistent environment, this would be queued for background processing

            # Create event loop if one doesn't exist
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Process new files (looking back 10 minutes to catch recent changes)
            result = loop.run_until_complete(
                document_ingestion_workflow.process_new_files(since_minutes=10)
            )

            logger.info(f"File processing triggered: {result['files_processed']} files processed")
            return True

        except Exception as e:
            logger.error(f"Error triggering file processing: {e}")
            return False

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.info(f"Drive webhook: {format % args}")


# Note: To set up Google Drive push notifications, you need to:
# 1. Enable the Google Drive API
# 2. Create a push notification channel
# 3. Configure the webhook URL in Google Drive API
#
# Example setup (to be run once):
# ```python
# from googleapiclient.discovery import build
#
# service = build('drive', 'v3', credentials=credentials)
#
# body = {
#     'id': 'telegram-assistant-drive-channel',
#     'type': 'web_hook',
#     'address': 'https://your-vercel-app.vercel.app/api/drive-webhook'
# }
#
# result = service.files().watch(
#     fileId='your_folder_id',
#     body=body
# ).execute()
# ```