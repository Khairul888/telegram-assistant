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
    from googleapiclient.discovery import build
    from google.oauth2.service_account import Credentials
    from googleapiclient.http import MediaIoBaseDownload
    from dotenv import load_dotenv
    import io
    import json
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
                self.model = genai.GenerativeModel('gemini-2.5-flash')
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

    async def classify_document(self, image_data: bytes) -> dict:
        """Classify document type using vision."""
        if not self.available:
            return {"error": "AI service not available"}

        try:
            # Convert bytes to PIL Image for Gemini
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(image_data))

            classification_prompt = """Look at this image and classify it as one of these document types:
- flight_ticket: Airline boarding passes, flight confirmations, e-tickets
- receipt: Restaurant bills, shopping receipts, purchase invoices
- hotel_booking: Hotel confirmations, accommodation bookings
- itinerary: Travel schedules, trip plans, tour bookings
- other_document: Any other travel-related document

Return only the classification type, nothing else."""

            response = self.model.generate_content([classification_prompt, image])

            classification = response.text.strip().lower() if response.text else "other_document"

            # Validate classification
            valid_types = ["flight_ticket", "receipt", "hotel_booking", "itinerary", "other_document"]
            if classification not in valid_types:
                classification = "other_document"

            return {
                "success": True,
                "document_type": classification,
                "confidence": 0.85  # Placeholder confidence score
            }
        except Exception as e:
            return {"success": False, "error": f"Classification error: {str(e)}"}

    async def extract_flight_details(self, image_data: bytes) -> dict:
        """Extract flight information from ticket images."""
        if not self.available:
            return {"error": "AI service not available"}

        try:
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(image_data))

            flight_prompt = """Analyze this flight ticket/boarding pass image and extract the following information.
Return ONLY a valid JSON object with these fields (use null for missing information):

{
    "airline": "airline name",
    "flight_number": "flight code",
    "departure_city": "departure city name",
    "departure_airport": "departure airport code",
    "arrival_city": "arrival city name",
    "arrival_airport": "arrival airport code",
    "departure_date": "YYYY-MM-DD",
    "departure_time": "HH:MM",
    "arrival_date": "YYYY-MM-DD",
    "arrival_time": "HH:MM",
    "gate": "gate number",
    "seat": "seat number",
    "booking_reference": "confirmation code",
    "passenger_name": "passenger name",
    "class": "travel class"
}"""

            response = self.model.generate_content([flight_prompt, image])

            if response.text:
                # Try to parse JSON response
                import json
                try:
                    extracted_data = json.loads(response.text.strip())
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.8
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Flight extraction error: {str(e)}"}

    async def extract_receipt_details(self, image_data: bytes) -> dict:
        """Extract expense data from receipt images."""
        if not self.available:
            return {"error": "AI service not available"}

        try:
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(image_data))

            receipt_prompt = """Analyze this receipt image and extract the following information.
Return ONLY a valid JSON object with these fields (use null for missing information):

{
    "merchant_name": "business name",
    "location": "address or city",
    "date": "YYYY-MM-DD",
    "time": "HH:MM",
    "items": [
        {"name": "item name", "price": 0.00, "quantity": 1}
    ],
    "subtotal": 0.00,
    "tax": 0.00,
    "tip": 0.00,
    "total": 0.00,
    "currency": "USD",
    "category": "food|transport|accommodation|entertainment|shopping",
    "payment_method": "cash|card|digital"
}"""

            response = self.model.generate_content([receipt_prompt, image])

            if response.text:
                import json
                try:
                    extracted_data = json.loads(response.text.strip())
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.85
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Receipt extraction error: {str(e)}"}

    async def extract_hotel_details(self, image_data: bytes) -> dict:
        """Extract hotel booking information."""
        if not self.available:
            return {"error": "AI service not available"}

        try:
            from PIL import Image
            import io

            image = Image.open(io.BytesIO(image_data))

            hotel_prompt = """Analyze this hotel booking confirmation and extract the following information.
Return ONLY a valid JSON object with these fields (use null for missing information):

{
    "hotel_name": "hotel name",
    "location": "city and address",
    "check_in_date": "YYYY-MM-DD",
    "check_in_time": "HH:MM",
    "check_out_date": "YYYY-MM-DD",
    "check_out_time": "HH:MM",
    "nights": 0,
    "room_type": "room type",
    "guests": 0,
    "booking_reference": "confirmation number",
    "total_cost": 0.00,
    "currency": "USD",
    "guest_name": "guest name"
}"""

            response = self.model.generate_content([hotel_prompt, image])

            if response.text:
                import json
                try:
                    extracted_data = json.loads(response.text.strip())
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.8
                    }
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Hotel extraction error: {str(e)}"}

    async def process_document(self, image_data: bytes, document_type: str = None) -> dict:
        """Process document based on type or auto-classify."""
        try:
            # Auto-classify if type not provided
            if not document_type:
                classification_result = await self.classify_document(image_data)
                if not classification_result.get("success"):
                    return classification_result
                document_type = classification_result["document_type"]

            # Route to appropriate extraction method
            if document_type == "flight_ticket":
                return await self.extract_flight_details(image_data)
            elif document_type == "receipt":
                return await self.extract_receipt_details(image_data)
            elif document_type == "hotel_booking":
                return await self.extract_hotel_details(image_data)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported document type: {document_type}"
                }

        except Exception as e:
            return {"success": False, "error": f"Document processing error: {str(e)}"}


class GoogleDriveService:
    """Google Drive API service for file operations."""

    def __init__(self):
        if DEPENDENCIES_AVAILABLE:
            try:
                # Get service account credentials
                service_account_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON_PATH')

                if service_account_path and os.path.exists(service_account_path):
                    credentials = Credentials.from_service_account_file(
                        service_account_path,
                        scopes=['https://www.googleapis.com/auth/drive.readonly']
                    )
                    self.service = build('drive', 'v3', credentials=credentials)
                    self.available = True
                else:
                    # Try to load from environment variable as JSON string
                    service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
                    if service_account_json:
                        service_account_info = json.loads(service_account_json)
                        credentials = Credentials.from_service_account_info(
                            service_account_info,
                            scopes=['https://www.googleapis.com/auth/drive.readonly']
                        )
                        self.service = build('drive', 'v3', credentials=credentials)
                        self.available = True
                    else:
                        self.available = False
                        print("No Google service account credentials found")
            except Exception as e:
                self.available = False
                print(f"Error initializing Google Drive service: {e}")
        else:
            self.available = False

    async def download_file(self, file_id: str) -> bytes:
        """Download file content from Google Drive."""
        if not self.available:
            raise Exception("Google Drive service not available")

        try:
            request = self.service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)

            done = False
            while done is False:
                status, done = downloader.next_chunk()

            file_io.seek(0)
            return file_io.read()
        except Exception as e:
            raise Exception(f"Error downloading file from Drive: {str(e)}")

    async def get_file_info(self, file_id: str) -> dict:
        """Get file metadata from Google Drive."""
        if not self.available:
            return {"error": "Google Drive service not available"}

        try:
            file_info = self.service.files().get(
                fileId=file_id,
                fields='id,name,mimeType,size,createdTime,modifiedTime'
            ).execute()
            return file_info
        except Exception as e:
            return {"error": f"Error getting file info: {str(e)}"}


class JobProcessor:
    """Process queued files with AI vision extraction."""

    def __init__(self, supabase_client, gemini_service, drive_service):
        self.supabase = supabase_client
        self.gemini = gemini_service
        self.drive = drive_service

    async def get_pending_jobs(self, limit: int = 5) -> list:
        """Get pending processing jobs from queue."""
        try:
            result = self.supabase.table('processing_jobs').select("*").eq('status', 'queued').limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting pending jobs: {e}")
            return []

    async def update_job_status(self, job_id: int, status: str, error_message: str = None) -> bool:
        """Update job status in database."""
        try:
            update_data = {
                "status": status,
                "started_at": datetime.now().isoformat() if status == "processing" else None,
                "completed_at": datetime.now().isoformat() if status in ["completed", "failed"] else None
            }
            if error_message:
                update_data["error_message"] = error_message

            self.supabase.table('processing_jobs').update(update_data).eq('id', job_id).execute()
            return True
        except Exception as e:
            print(f"Error updating job status: {e}")
            return False

    async def process_single_job(self, job_data: dict) -> dict:
        """Process a single job from the queue."""
        job_id = job_data.get('id')
        file_id = job_data.get('file_id')
        file_name = job_data.get('file_name')
        user_id = job_data.get('user_id')

        try:
            # Update job status to processing
            await self.update_job_status(job_id, "processing")

            # Download file from Google Drive
            print(f"Processing job {job_id}: {file_name}")
            file_data = await self.drive.download_file(file_id)

            # Process with Gemini vision
            extraction_result = await self.gemini.process_document(file_data)

            if extraction_result.get("success"):
                # Store extracted data
                storage_result = await self.store_extraction_results(job_id, user_id, extraction_result)

                if storage_result.get("success"):
                    await self.update_job_status(job_id, "completed")
                    return {
                        "success": True,
                        "job_id": job_id,
                        "message": f"Successfully processed {file_name}",
                        "extracted_data": extraction_result.get("data"),
                        "storage_result": storage_result
                    }
                else:
                    await self.update_job_status(job_id, "failed", f"Storage error: {storage_result.get('error')}")
                    return {"success": False, "error": f"Failed to store results: {storage_result.get('error')}"}
            else:
                await self.update_job_status(job_id, "failed", f"Extraction error: {extraction_result.get('error')}")
                return {"success": False, "error": f"Extraction failed: {extraction_result.get('error')}"}

        except Exception as e:
            error_msg = f"Job processing error: {str(e)}"
            await self.update_job_status(job_id, "failed", error_msg)
            return {"success": False, "error": error_msg}

    async def store_extraction_results(self, job_id: int, user_id: str, extraction_result: dict) -> dict:
        """Store extracted data in appropriate tables."""
        try:
            extracted_data = extraction_result.get("data", {})
            document_type = extraction_result.get("document_type", "unknown")
            confidence = extraction_result.get("confidence", 0.0)

            # Create document processing result record
            processing_result = {
                "processing_job_id": job_id,
                "document_type": document_type,
                "processing_status": "completed",
                "extraction_confidence": confidence,
                "ai_model_used": "gemini-2.5-flash",
                "structured_data": extracted_data,
                "completed_at": datetime.now().isoformat()
            }

            result = self.supabase.table('document_processing_results').insert(processing_result).execute()
            processing_result_id = result.data[0]['id'] if result.data else None

            # Store in specific table based on document type
            stored_record_id = None
            if document_type == "flight_ticket":
                stored_record_id = await self.store_flight_data(user_id, job_id, extracted_data, confidence)
            elif document_type == "receipt":
                stored_record_id = await self.store_expense_data(user_id, job_id, extracted_data, confidence)
            elif document_type == "hotel_booking":
                stored_record_id = await self.store_hotel_data(user_id, job_id, extracted_data, confidence)

            # Update processing result with linked record
            if stored_record_id and processing_result_id:
                update_data = {}
                if document_type == "flight_ticket" or document_type == "hotel_booking":
                    update_data["travel_event_id"] = stored_record_id
                elif document_type == "receipt":
                    update_data["expense_id"] = stored_record_id

                if update_data:
                    self.supabase.table('document_processing_results').update(update_data).eq('id', processing_result_id).execute()

            return {
                "success": True,
                "document_type": document_type,
                "record_id": stored_record_id,
                "processing_result_id": processing_result_id
            }

        except Exception as e:
            return {"success": False, "error": f"Storage error: {str(e)}"}

    async def store_flight_data(self, user_id: str, job_id: int, data: dict, confidence: float) -> int:
        """Store flight data in travel_events table."""
        try:
            # Parse dates and times
            departure_datetime = None
            arrival_datetime = None

            if data.get("departure_date") and data.get("departure_time"):
                departure_datetime = f"{data['departure_date']} {data['departure_time']}:00"
            if data.get("arrival_date") and data.get("arrival_time"):
                arrival_datetime = f"{data['arrival_date']} {data['arrival_time']}:00"

            flight_record = {
                "user_id": user_id,
                "processing_job_id": job_id,
                "event_type": "flight",
                "title": f"{data.get('airline', 'Flight')} {data.get('flight_number', '')}".strip(),
                "airline": data.get("airline"),
                "flight_number": data.get("flight_number"),
                "departure_airport": data.get("departure_airport"),
                "arrival_airport": data.get("arrival_airport"),
                "departure_city": data.get("departure_city"),
                "arrival_city": data.get("arrival_city"),
                "departure_time": departure_datetime,
                "arrival_time": arrival_datetime,
                "start_date": departure_datetime,
                "end_date": arrival_datetime,
                "gate": data.get("gate"),
                "seat": data.get("seat"),
                "booking_reference": data.get("booking_reference"),
                "passenger_name": data.get("passenger_name"),
                "confidence_score": confidence,
                "raw_extracted_data": data
            }

            result = self.supabase.table('travel_events').insert(flight_record).execute()
            return result.data[0]['id'] if result.data else None

        except Exception as e:
            print(f"Error storing flight data: {e}")
            return None

    async def store_expense_data(self, user_id: str, job_id: int, data: dict, confidence: float) -> int:
        """Store expense data in expenses table."""
        try:
            expense_record = {
                "user_id": user_id,
                "processing_job_id": job_id,
                "merchant_name": data.get("merchant_name"),
                "location": data.get("location"),
                "transaction_date": data.get("date"),
                "transaction_time": data.get("time"),
                "category": data.get("category", "other"),
                "subtotal": float(data.get("subtotal", 0)) if data.get("subtotal") else None,
                "tax_amount": float(data.get("tax", 0)) if data.get("tax") else None,
                "tip_amount": float(data.get("tip", 0)) if data.get("tip") else None,
                "total_amount": float(data.get("total", 0)) if data.get("total") else None,
                "currency": data.get("currency", "USD"),
                "items": data.get("items", []),
                "payment_method": data.get("payment_method"),
                "confidence_score": confidence,
                "raw_extracted_data": data
            }

            result = self.supabase.table('expenses').insert(expense_record).execute()
            return result.data[0]['id'] if result.data else None

        except Exception as e:
            print(f"Error storing expense data: {e}")
            return None

    async def store_hotel_data(self, user_id: str, job_id: int, data: dict, confidence: float) -> int:
        """Store hotel data in travel_events table."""
        try:
            hotel_record = {
                "user_id": user_id,
                "processing_job_id": job_id,
                "event_type": "hotel",
                "title": data.get("hotel_name", "Hotel Booking"),
                "hotel_name": data.get("hotel_name"),
                "location": data.get("location"),
                "check_in_date": data.get("check_in_date"),
                "check_out_date": data.get("check_out_date"),
                "start_date": f"{data.get('check_in_date')} {data.get('check_in_time', '15:00')}:00" if data.get("check_in_date") else None,
                "end_date": f"{data.get('check_out_date')} {data.get('check_out_time', '11:00')}:00" if data.get("check_out_date") else None,
                "room_type": data.get("room_type"),
                "nights": int(data.get("nights", 0)) if data.get("nights") else None,
                "guests": int(data.get("guests", 1)) if data.get("guests") else None,
                "booking_reference": data.get("booking_reference"),
                "guest_name": data.get("guest_name"),
                "confidence_score": confidence,
                "raw_extracted_data": data
            }

            result = self.supabase.table('travel_events').insert(hotel_record).execute()
            return result.data[0]['id'] if result.data else None

        except Exception as e:
            print(f"Error storing hotel data: {e}")
            return None

    async def process_pending_jobs(self, max_jobs: int = 5) -> dict:
        """Process multiple pending jobs."""
        try:
            pending_jobs = await self.get_pending_jobs(max_jobs)

            if not pending_jobs:
                return {"success": True, "message": "No pending jobs to process", "processed": 0}

            results = []
            successful = 0
            failed = 0

            for job in pending_jobs:
                result = await self.process_single_job(job)
                results.append(result)

                if result.get("success"):
                    successful += 1
                else:
                    failed += 1

            return {
                "success": True,
                "processed": len(pending_jobs),
                "successful": successful,
                "failed": failed,
                "results": results
            }

        except Exception as e:
            return {"success": False, "error": f"Batch processing error: {str(e)}"}


# Initialize services (will be done lazily)
job_queue = None
gemini_service = None
drive_service = None
job_processor = None


class handler(BaseHTTPRequestHandler):
    """Minimal Telegram webhook handler."""

    def do_POST(self):
        """Handle POST requests from Telegram webhook."""
        try:
            # Initialize services if not already done
            global job_queue, gemini_service, drive_service, job_processor
            if job_queue is None:
                job_queue = SupabaseJobQueue()
            if gemini_service is None:
                gemini_service = SimpleGeminiService()
            if drive_service is None:
                drive_service = GoogleDriveService()
            if job_processor is None and job_queue.available and gemini_service.available and drive_service.available:
                job_processor = JobProcessor(job_queue.supabase, gemini_service, drive_service)
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
        try:
            # Initialize services if not already done
            global job_queue, gemini_service, drive_service, job_processor
            if job_queue is None:
                job_queue = SupabaseJobQueue()
            if gemini_service is None:
                gemini_service = SimpleGeminiService()
            if drive_service is None:
                drive_service = GoogleDriveService()
            if job_processor is None and job_queue.available and gemini_service.available and drive_service.available:
                job_processor = JobProcessor(job_queue.supabase, gemini_service, drive_service)

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
                    "gemini": gemini_service.available if gemini_service else False,
                    "job_queue": job_queue.available if job_queue else False,
                    "google_drive": drive_service.available if drive_service else False
                }
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode('utf-8'))

    def extract_message_info(self, update):
        """Extract basic message information from update."""
        try:
            if "message" in update:
                message = update["message"]

                # Extract basic info
                chat_id = message["chat"]["id"]
                message_id = message["message_id"]

                # Security: Only allow your chat ID
                ALLOWED_CHAT_IDS = [1316304260]  # Your chat ID
                if chat_id not in ALLOWED_CHAT_IDS:
                    print(f"Unauthorized access attempt from chat_id: {chat_id}")
                    return None

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

            elif user_content.lower().startswith('/process'):
                response_text = await self._handle_process_command(first_name)

            elif user_content.lower().startswith('/debug'):
                response_text = await self._handle_debug_command(first_name)

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
🔄 `/process` - Process pending files
🔍 `/debug` - Show processing errors

**Upload pics of:**
✈️ Tickets, bookings, itineraries
🧾 Receipts, bills

**Ask me stuff like:**
• "When's our flight?"
• "What did we spend on food?"
• "Show me hotel details"

Phase 2B: AI vision processing active!
Upload pics and use /process to extract details."""

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

    async def _handle_process_command(self, first_name: str) -> str:
        """Handle /process command to manually trigger job processing."""
        try:
            global job_processor

            if not job_processor:
                return f"🔄 Processing service not available. Make sure all services are connected."

            # Process pending jobs
            result = await job_processor.process_pending_jobs(max_jobs=3)

            if result.get("success"):
                processed = result.get("processed", 0)
                successful = result.get("successful", 0)
                failed = result.get("failed", 0)

                if processed == 0:
                    return f"✅ No pending files to process, {first_name}!"
                else:
                    return f"""🔄 **Processing Complete!**

📊 **Results:**
• Processed: {processed} files
• ✅ Successful: {successful}
• ❌ Failed: {failed}

Files have been analyzed and travel details extracted! Try asking me about your trips or expenses."""
            else:
                return f"❌ Processing failed: {result.get('error', 'Unknown error')}"

        except Exception as e:
            return f"⚠️ **Processing Error**\n\nError: {str(e)}"

    async def _handle_debug_command(self, first_name: str) -> str:
        """Handle /debug command to show recent job errors."""
        try:
            global job_queue

            if not job_queue or not job_queue.available:
                return f"❌ Job queue not available for debugging."

            # Get recent failed jobs
            result = job_queue.supabase.table('processing_jobs').select("*").eq('status', 'failed').order('created_at', desc=True).limit(3).execute()

            if not result.data:
                return f"✅ No recent failed jobs found!"

            debug_info = f"🔍 **Recent Failed Jobs:**\n\n"

            for job in result.data:
                debug_info += f"**File:** {job.get('file_name', 'Unknown')}\n"
                debug_info += f"**Error:** {job.get('error_message', 'No error message')}\n"
                debug_info += f"**Time:** {job.get('created_at', 'Unknown')}\n\n"

            return debug_info

        except Exception as e:
            return f"⚠️ **Debug Error**\n\nError: {str(e)}"

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