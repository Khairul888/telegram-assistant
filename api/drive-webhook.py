"""
Enhanced Google Drive webhook for Vercel deployment.
Phase 2: File processing with Google Drive API integration.
"""

from http.server import BaseHTTPRequestHandler
import json
import os
import sys
from pathlib import Path
from datetime import datetime
import asyncio

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'src'))

try:
    from supabase import create_client, Client
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials
    from googleapiclient.http import MediaIoBaseDownload
    from dotenv import load_dotenv
    import io
    DEPENDENCIES_AVAILABLE = True
except ImportError as e:
    DEPENDENCIES_AVAILABLE = False
    print(f"Import error: {e}")

# Load environment variables
load_dotenv()


class EnhancedDriveWebhook:
    """Enhanced Google Drive webhook handler with file processing."""

    def __init__(self):
        self.supabase = None
        self.drive_service = None
        self.available = False

        if DEPENDENCIES_AVAILABLE:
            # Initialize Supabase
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')

            if supabase_url and supabase_key:
                self.supabase = create_client(supabase_url, supabase_key)

                # Initialize Google Drive service
                try:
                    service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_PATH')

                    if service_account_path and os.path.exists(service_account_path):
                        credentials = Credentials.from_service_account_file(
                            service_account_path,
                            scopes=['https://www.googleapis.com/auth/drive.readonly']
                        )
                        self.drive_service = build('drive', 'v3', credentials=credentials)
                        self.available = True
                    else:
                        # Try environment variable
                        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
                        if service_account_json:
                            service_account_info = json.loads(service_account_json)
                            credentials = Credentials.from_service_account_info(
                                service_account_info,
                                scopes=['https://www.googleapis.com/auth/drive.readonly']
                            )
                            self.drive_service = build('drive', 'v3', credentials=credentials)
                            self.available = True
                        else:
                            print("No Google service account credentials found")
                except Exception as e:
                    print(f"Error initializing Google Drive service: {e}")
            else:
                print("Supabase credentials not found")

    def is_supported_file(self, file_info: dict) -> bool:
        """Check if file type is supported for processing."""
        if not file_info.get('mimeType'):
            return False

        supported_types = [
            'image/jpeg',
            'image/png',
            'image/gif',
            'application/pdf'
        ]
        return file_info['mimeType'] in supported_types

    async def get_file_info(self, file_id: str) -> dict:
        """Get file metadata from Google Drive."""
        if not self.available or not self.drive_service:
            return {"error": "Drive service not available"}

        try:
            file_info = self.drive_service.files().get(
                fileId=file_id,
                fields='id,name,mimeType,size,createdTime,modifiedTime,parents'
            ).execute()
            return file_info
        except Exception as e:
            return {"error": f"Error getting file info: {str(e)}"}

    async def create_processing_job(self, file_info: dict, user_id: str = "system") -> dict:
        """Create a processing job for the file."""
        if not self.available or not self.supabase:
            return {"success": False, "error": "Database not available"}

        try:
            # Determine document type based on file name and location
            file_name = file_info.get('name', '').lower()

            # Simple heuristics for document classification
            if any(word in file_name for word in ['ticket', 'flight', 'boarding']):
                doc_type = 'flight_ticket'
            elif any(word in file_name for word in ['receipt', 'bill', 'invoice']):
                doc_type = 'receipt'
            elif any(word in file_name for word in ['hotel', 'booking', 'reservation']):
                doc_type = 'hotel_booking'
            else:
                doc_type = 'travel_document'

            job_data = {
                "file_name": file_info.get('name'),
                "file_id": file_info.get('id'),
                "user_id": user_id,
                "status": "queued",
                "file_type": doc_type,
                "file_size": int(file_info.get('size', 0)),
                "created_at": datetime.now().isoformat(),
            }

            result = self.supabase.table('processing_jobs').insert(job_data).execute()

            return {
                "success": True,
                "job_id": result.data[0]['id'] if result.data else None,
                "message": f"Processing job created for {doc_type}",
                "document_type": doc_type
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_drive_event(self, event_data: dict) -> dict:
        """Process Google Drive webhook event."""
        if not self.available:
            return {"success": False, "error": "Services not available"}

        resource_state = event_data.get('resource_state')
        resource_id = event_data.get('resource_id')

        # Only process 'add' and 'update' events for new files
        if resource_state not in ['add', 'update'] or not resource_id:
            return {"success": True, "message": "Event ignored - not a file addition"}

        try:
            # Get file information
            file_info = await self.get_file_info(resource_id)

            if "error" in file_info:
                return {"success": False, "error": file_info["error"]}

            # Check if it's in our monitored folder
            monitored_folder = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
            if monitored_folder and monitored_folder not in str(file_info.get('parents', [])):
                return {"success": True, "message": "File not in monitored folder"}

            # Check if file type is supported
            if not self.is_supported_file(file_info):
                return {"success": True, "message": f"File type {file_info.get('mimeType')} not supported"}

            # Create processing job
            job_result = await self.create_processing_job(file_info)

            if job_result["success"]:
                return {
                    "success": True,
                    "message": f"Created processing job for {file_info.get('name')}",
                    "job_id": job_result.get("job_id"),
                    "document_type": job_result.get("document_type"),
                    "file_info": {
                        "name": file_info.get('name'),
                        "size": file_info.get('size'),
                        "type": file_info.get('mimeType')
                    }
                }
            else:
                return job_result

        except Exception as e:
            return {"success": False, "error": f"Error processing event: {str(e)}"}


# Initialize webhook handler
drive_webhook = EnhancedDriveWebhook()


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

            # Phase 2: Process files automatically
            if DEPENDENCIES_AVAILABLE and drive_webhook.available:
                # Try to create event loop for async operation
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                # Process the Drive event
                process_result = loop.run_until_complete(drive_webhook.process_drive_event(event_data))
                response_data = {
                    "status": "processed",
                    "message": "Drive event processed successfully",
                    "phase": "Phase 2 - File Processing",
                    "process_result": process_result,
                    "resource_state": resource_state
                }
            else:
                response_data = {
                    "status": "received",
                    "message": "Webhook received but processing unavailable",
                    "phase": "Phase 2 - Service Unavailable",
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
                "message": "Google Drive webhook endpoint with file processing",
                "phase": "Phase 2 - File Processing",
                "features": ["Auto file detection", "Processing job creation", "Document classification"],
                "endpoint": "/api/drive-webhook",
                "dependencies_available": DEPENDENCIES_AVAILABLE,
                "services": {
                    "enhanced_webhook": drive_webhook.available if 'drive_webhook' in globals() else False,
                    "google_drive": hasattr(drive_webhook, 'drive_service') and drive_webhook.drive_service is not None if 'drive_webhook' in globals() else False,
                    "supabase": hasattr(drive_webhook, 'supabase') and drive_webhook.supabase is not None if 'drive_webhook' in globals() else False
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