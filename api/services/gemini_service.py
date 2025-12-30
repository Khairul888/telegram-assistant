"""Gemini AI service for OCR and text generation."""
import os
import json
from PIL import Image
import io

try:
    from google import genai
    from google.genai import types
    from google.oauth2.service_account import Credentials
    import pypdfium2 as pdfium
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False
    print("Warning: google-genai or pypdfium2 not available")


class GeminiService:
    """Gemini AI service for document processing and Q&A."""

    def __init__(self):
        """Initialize Gemini with Vertex AI service account."""
        if not DEPENDENCIES_AVAILABLE:
            self.available = False
            print("Warning: Required packages not available")
            return

        # Primary: Vertex AI with service account
        if self._init_vertex_ai():
            self.available = True
            self.backend = "vertex_ai"
            print(f"Initialized: Vertex AI ({os.getenv('GCP_PROJECT_ID')})")
            return

        # === FALLBACK CODE (COMMENTED OUT) ===
        # Uncomment below to enable Gemini API fallback if Vertex AI fails
        # if self._init_gemini_api():
        #     self.available = True
        #     self.backend = "gemini_api"
        #     print("Initialized: Gemini API (fallback)")
        #     return

        # If we reach here, Vertex AI failed and fallback is disabled
        self.available = False
        print("ERROR: Vertex AI initialization failed. Check credentials:")
        print("  - GCP_PROJECT_ID")
        print("  - GCP_LOCATION")
        print("  - GOOGLE_CLIENT_EMAIL")
        print("  - GOOGLE_PRIVATE_KEY")

    def _init_vertex_ai(self) -> bool:
        """Initialize with Vertex AI + service account."""
        try:
            project_id = os.getenv('GCP_PROJECT_ID')
            location = os.getenv('GCP_LOCATION', 'us-central1')
            client_email = os.getenv('GOOGLE_CLIENT_EMAIL')
            private_key = os.getenv('GOOGLE_PRIVATE_KEY')

            if not all([project_id, client_email, private_key]):
                print("Vertex AI credentials incomplete")
                return False

            # Build service account credentials dictionary
            credentials_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key_id": "key-1",  # Placeholder, not validated by Google
                "private_key": private_key.replace('\\n', '\n'),  # Normalize newlines
                "client_email": client_email,
                "client_id": "",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            }

            # Create credentials from service account info
            credentials = Credentials.from_service_account_info(
                credentials_dict,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )

            # Initialize google-genai client with Vertex AI backend
            self.client = genai.Client(
                vertexai=True,
                project=project_id,
                location=location,
                credentials=credentials,
                http_options={'api_version': 'v1'}
            )

            return True

        except Exception as e:
            print(f"Vertex AI init error: {e}")
            return False

    def _init_gemini_api(self) -> bool:
        """Initialize with Gemini API + API key (FALLBACK - currently disabled)."""
        try:
            api_key = os.getenv('GOOGLE_GEMINI_API_KEY')
            if not api_key:
                return False

            self.client = genai.Client(api_key=api_key)
            return True

        except Exception as e:
            print(f"Gemini API init error: {e}")
            return False

    def _extract_json_from_response(self, text: str) -> dict:
        """
        Extract JSON from AI response that might be wrapped in markdown or have extra text.

        Args:
            text: Raw AI response text

        Returns:
            dict: Parsed JSON data

        Raises:
            json.JSONDecodeError: If no valid JSON found
        """
        if not text:
            raise json.JSONDecodeError("Empty response", "", 0)

        # Try to parse as-is first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        import re

        # Pattern 1: ```json ... ```
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Pattern 2: Find first { to last }
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                pass

        # If all else fails, raise error with the original text
        raise json.JSONDecodeError(f"Could not extract JSON from response: {text[:200]}...", text, 0)

    def _validate_and_open_image(self, image_data: bytes):
        """
        Validate and open image data with PIL.

        Args:
            image_data: Image bytes

        Returns:
            PIL.Image: Opened image

        Raises:
            ValueError: If image data is invalid
        """
        if not image_data:
            raise ValueError("Empty image data received")

        if len(image_data) < 100:
            raise ValueError(f"Image data too small: {len(image_data)} bytes")

        print(f"Processing image: {len(image_data)} bytes")

        # Create BytesIO and open image
        image_buffer = io.BytesIO(image_data)

        try:
            image = Image.open(image_buffer)
            image.verify()  # Verify it's a valid image

            # Reopen after verify (verify closes the file)
            image_buffer.seek(0)
            image = Image.open(image_buffer)

            print(f"Image opened successfully: {image.format} {image.size}")
            return image
        except Exception as img_error:
            raise ValueError(f"Invalid image format: {str(img_error)}. Received {len(image_data)} bytes.")

    async def generate_response(self, prompt: str, system_instruction: str = None) -> str:
        """
        Generate AI text response with optional system instruction.

        Args:
            prompt: User question/prompt
            system_instruction: Optional context/system message

        Returns:
            str: AI-generated response
        """
        if not self.available:
            return "AI service temporarily unavailable. Please try again later."

        try:
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\nUser: {prompt}"

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt
            )
            return response.text if response.text else "I'm unable to generate a response right now."
        except Exception as e:
            return f"AI service error: {str(e)}"

    async def classify_document(self, image_data: bytes) -> dict:
        """
        Classify document type using vision.

        Args:
            image_data: Image file bytes

        Returns:
            dict: {"success": bool, "document_type": str, "confidence": float}
        """
        if not self.available:
            return {"success": False, "error": "AI service not available"}

        try:
            # Validate and open image
            image = self._validate_and_open_image(image_data)

            classification_prompt = """Look at this image and classify it as one of these document types:
- flight_ticket: Airline boarding passes, flight confirmations, e-tickets
- receipt: Restaurant bills, shopping receipts, purchase invoices
- hotel_booking: Hotel confirmations, accommodation bookings
- itinerary: Travel schedules, trip plans, tour bookings
- other_document: Any other travel-related document

Return only the classification type, nothing else. Do not use bold formatting or include reasoning."""

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[classification_prompt, image]
            )

            classification = response.text.strip().lower() if response.text else "other_document"

            # Validate classification
            valid_types = ["flight_ticket", "receipt", "hotel_booking", "itinerary", "other_document"]
            if classification not in valid_types:
                classification = "other_document"

            return {
                "success": True,
                "document_type": classification,
                "confidence": 0.85
            }
        except Exception as e:
            return {"success": False, "error": f"Classification error: {str(e)}"}

    async def extract_flight_details(self, image_data: bytes) -> dict:
        """
        Extract flight information from ticket images.

        Args:
            image_data: Flight ticket image bytes

        Returns:
            dict: {"success": bool, "data": dict, "confidence": float}
        """
        if not self.available:
            return {"success": False, "error": "AI service not available"}

        try:
            image = self._validate_and_open_image(image_data)

            flight_prompt = """Analyze this flight ticket/boarding pass image and extract the following information.
Return ONLY a valid JSON object with these fields (use null for missing information):

{
    "airline": "airline name",
    "flight_number": "flight code",
    "departure_city": "departure city name",
    "departure_airport": "departure airport code",
    "departure_terminal": "departure terminal (e.g., Terminal 1, Terminal A, T2)",
    "arrival_city": "arrival city name",
    "arrival_airport": "arrival airport code",
    "arrival_terminal": "arrival terminal (e.g., Terminal 3, Terminal B, T4)",
    "departure_date": "YYYY-MM-DD",
    "departure_time": "HH:MM",
    "arrival_date": "YYYY-MM-DD",
    "arrival_time": "HH:MM",
    "gate": "gate number",
    "seat": "seat number",
    "booking_reference": "confirmation code",
    "passenger_name": "passenger name",
    "class": "travel class"
}

Do not use bold formatting or include reasoning."""

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[flight_prompt, image]
            )

            if response.text:
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
        """
        Extract expense data from receipt images.

        Args:
            image_data: Receipt image bytes

        Returns:
            dict: {"success": bool, "data": dict, "confidence": float}
        """
        if not self.available:
            return {"success": False, "error": "AI service not available"}

        try:
            image = self._validate_and_open_image(image_data)

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
}

Do not use bold formatting or include reasoning."""

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[receipt_prompt, image]
            )

            if response.text:
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
        """
        Extract hotel booking information.

        Args:
            image_data: Hotel booking image bytes

        Returns:
            dict: {"success": bool, "data": dict, "confidence": float}
        """
        if not self.available:
            return {"success": False, "error": "AI service not available"}

        try:
            image = self._validate_and_open_image(image_data)

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
}

Do not use bold formatting or include reasoning."""

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[hotel_prompt, image]
            )

            if response.text:
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

    async def process_pdf(self, pdf_data: bytes, document_type: str = None) -> dict:
        """
        Process multi-page PDF document.

        Strategy 1 (Primary): Convert PDF to images inline, process with Vertex AI
        Strategy 2 (Fallback): Use Gemini API File API (activate if Strategy 1 fails)

        Args:
            pdf_data: PDF file bytes
            document_type: Optional pre-classified type

        Returns:
            dict: Extraction result with document_type and extracted data
        """
        if not self.available:
            return {"success": False, "error": "AI service not available"}

        # === STRATEGY SELECTOR ===
        # Toggle between inline conversion vs File API
        USE_INLINE_PDF_CONVERSION = True  # Change to False to use File API fallback

        if USE_INLINE_PDF_CONVERSION:
            return await self._process_pdf_inline(pdf_data, document_type)
        else:
            return await self._process_pdf_file_api(pdf_data, document_type)

    async def _process_pdf_inline(self, pdf_data: bytes, document_type: str = None) -> dict:
        """Strategy 1: Convert PDF pages to images and process inline (Vertex AI compatible)."""
        try:
            print(f"Processing PDF inline: {len(pdf_data)} bytes")

            # Validate PDF data
            if not pdf_data or len(pdf_data) < 100:
                return {"success": False, "error": f"Invalid PDF data: {len(pdf_data)} bytes"}

            # Convert PDF to images using pypdfium2
            pdf = pdfium.PdfDocument(pdf_data)
            print(f"PDF loaded: {len(pdf)} pages")

            # Convert all pages to PIL Images
            images = []
            for page_num in range(len(pdf)):
                page = pdf[page_num]
                bitmap = page.render(scale=2.0)  # 2x resolution for better OCR
                pil_image = bitmap.to_pil()
                images.append(pil_image)

            print(f"Converted {len(images)} pages to images")

            # Classify document type if not provided
            if not document_type:
                classification_prompt = """Analyze ALL PAGES of this document and classify it as one of these types:
- flight_ticket: Airline boarding passes, flight confirmations, e-tickets
- receipt: Restaurant bills, shopping receipts, purchase invoices
- hotel_booking: Hotel confirmations, accommodation bookings
- itinerary: Travel schedules, trip plans, tour bookings
- other_document: Any other travel-related document

Return only the classification type, nothing else. Do not use bold formatting or include reasoning."""

                contents = [classification_prompt] + images
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=contents
                )

                classification = response.text.strip().lower() if response.text else "other_document"
                valid_types = ["flight_ticket", "receipt", "hotel_booking", "itinerary", "other_document"]
                if classification not in valid_types:
                    classification = "other_document"

                document_type = classification
                print(f"Classified as: {document_type}")

            # Extract data based on document type
            if document_type == "flight_ticket":
                result = await self._extract_flight_from_pdf_inline(images)
            elif document_type == "receipt":
                result = await self._extract_receipt_from_pdf_inline(images)
            elif document_type == "hotel_booking":
                result = await self._extract_hotel_from_pdf_inline(images)
            else:
                result = {"success": True, "data": {}, "confidence": 0.5}

            if result.get("success"):
                result["document_type"] = document_type

            return result

        except Exception as e:
            print(f"Inline PDF processing error: {e}")
            return {"success": False, "error": f"PDF processing error: {str(e)}"}

    async def _process_pdf_file_api(self, pdf_data: bytes, document_type: str = None) -> dict:
        """
        Strategy 2: Use Gemini API File API for PDF processing (FALLBACK).

        NOTE: This requires GOOGLE_GEMINI_API_KEY and uses Gemini API backend.
        File API is NOT supported on Vertex AI.
        """
        try:
            print(f"Processing PDF via File API: {len(pdf_data)} bytes")

            # Validate PDF data
            if not pdf_data or len(pdf_data) < 100:
                return {"success": False, "error": f"Invalid PDF data: {len(pdf_data)} bytes"}

            # Check if we have API key for File API
            api_key = os.getenv('GOOGLE_GEMINI_API_KEY')
            if not api_key:
                return {
                    "success": False,
                    "error": "File API fallback requires GOOGLE_GEMINI_API_KEY. Either set the API key or use inline PDF conversion (USE_INLINE_PDF_CONVERSION=True)."
                }

            # Create separate Gemini API client for File API
            file_api_client = genai.Client(api_key=api_key)

            # Upload PDF using File API
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', mode='wb') as tmp_file:
                tmp_file.write(pdf_data)
                tmp_path = tmp_file.name

            try:
                print(f"Uploading PDF to Gemini File API...")
                uploaded_file = file_api_client.files.upload(
                    path=tmp_path,
                    config=types.UploadFileConfig(
                        mime_type="application/pdf",
                        display_name="travel_document.pdf"
                    )
                )
                print(f"PDF uploaded: {uploaded_file.name}")

                # Wait for processing
                import time
                while uploaded_file.state.name == "PROCESSING":
                    print("Waiting for file processing...")
                    time.sleep(1)
                    uploaded_file = file_api_client.files.get(name=uploaded_file.name)

                if uploaded_file.state.name == "FAILED":
                    return {"success": False, "error": "File processing failed"}

                # Classify and extract (using existing _extract_*_from_pdf methods)
                # These methods will need uploaded_file parameter instead of images
                # NOTE: Would need to update those methods to accept either format

                # For now, return error indicating this needs implementation
                return {
                    "success": False,
                    "error": "File API fallback not fully implemented. Use inline PDF conversion instead."
                }

            finally:
                # Cleanup temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        except Exception as e:
            print(f"File API PDF processing error: {e}")
            return {"success": False, "error": f"PDF processing error: {str(e)}"}

    async def _extract_flight_from_pdf_inline(self, images: list) -> dict:
        """Extract flight details from PDF images."""
        try:
            flight_prompt = """You are a precise data extraction expert. Carefully read ALL PAGES of this flight document (boarding pass, e-ticket, or flight confirmation).

INSTRUCTIONS:
1. Extract EXACT text as it appears - do not paraphrase or abbreviate
2. For dates, convert to YYYY-MM-DD format
3. For times, use 24-hour HH:MM format
4. IMPORTANT: If this is a ROUND-TRIP ticket, extract BOTH the outbound AND return flights
5. For multi-city trips, extract ALL flight segments
6. Check header, footer, and all sections of ALL pages
7. Each flight should be a separate object in the flights array

Extract ALL flights and return ONLY a valid JSON object (no markdown, no explanation):

{
    "flights": [
        {
            "airline": "full airline name exactly as shown",
            "flight_number": "flight code with letters and numbers (e.g., AA123, DL4567)",
            "departure_city": "full departure city name",
            "departure_airport": "3-letter IATA code (e.g., LAX, JFK)",
            "departure_terminal": "departure terminal (e.g., Terminal 1, Terminal A, T2)",
            "arrival_city": "full arrival city name",
            "arrival_airport": "3-letter IATA code",
            "arrival_terminal": "arrival terminal (e.g., Terminal 3, Terminal B, T4)",
            "departure_date": "YYYY-MM-DD format",
            "departure_time": "HH:MM in 24-hour format",
            "arrival_date": "YYYY-MM-DD format",
            "arrival_time": "HH:MM in 24-hour format",
            "gate": "gate number/letter if available",
            "seat": "seat assignment (e.g., 12A, 23F)",
            "booking_reference": "PNR/confirmation code (usually 6 characters)",
            "passenger_name": "passenger full name",
            "class": "cabin class (Economy, Business, First, etc.)"
        }
    ]
}

CRITICAL:
- For one-way tickets: flights array will have 1 object
- For round-trip tickets: flights array will have 2 objects (outbound first, return second)
- For multi-city: flights array will have multiple objects in chronological order
- Use null for any field not found in the document
- Booking reference is usually the SAME for all flights on the same reservation
- Do not use bold formatting or include reasoning"""

            contents = [flight_prompt] + images
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents
            )

            if response.text:
                try:
                    print(f"Raw flight response: {response.text[:500]}")
                    extracted_data = self._extract_json_from_response(response.text)
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.8
                    }
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {str(e)}")
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text[:500]
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Flight extraction error: {str(e)}"}

    async def _extract_receipt_from_pdf_inline(self, images: list) -> dict:
        """Extract receipt details from PDF images."""
        try:
            receipt_prompt = """You are a precise receipt data extraction expert. Carefully read ALL PAGES of this receipt/invoice document.

INSTRUCTIONS:
1. Extract merchant name EXACTLY as it appears (usually at top in large text)
2. Read ALL line items carefully - don't miss any
3. For prices, extract numeric values with 2 decimal places
4. Calculate subtotal by summing all item prices if not shown
5. CRITICAL: The TOTAL is the final amount paid - look for words like "Total", "Amount Due", "Balance", "Grand Total"
6. Check all pages for continuation of items or totals on subsequent pages
7. Distinguish between subtotal, tax, tip, and total carefully

Extract the following and return ONLY a valid JSON object (no markdown, no explanation):

{
    "merchant_name": "exact business name as shown",
    "location": "full address or at least city",
    "date": "YYYY-MM-DD format",
    "time": "HH:MM format (if available)",
    "items": [
        {"name": "exact item name", "price": 12.99, "quantity": 2}
    ],
    "subtotal": 0.00,
    "tax": 0.00,
    "tip": 0.00,
    "total": 0.00,
    "currency": "USD",
    "category": "food|transport|accommodation|entertainment|shopping",
    "payment_method": "cash|card|digital"
}

CRITICAL:
- items array must include ALL items from the receipt
- subtotal = sum of all item prices (before tax/tip)
- total = final amount paid (subtotal + tax + tip)
- If only total is shown, use that and set subtotal = total
- Use null for any field not found in the document
- Do not use bold formatting or include reasoning"""

            contents = [receipt_prompt] + images
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents
            )

            if response.text:
                try:
                    print(f"Raw receipt response: {response.text[:500]}")
                    extracted_data = self._extract_json_from_response(response.text)
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.85
                    }
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {str(e)}")
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text[:500]
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Receipt extraction error: {str(e)}"}

    async def _extract_hotel_from_pdf_inline(self, images: list) -> dict:
        """Extract hotel booking details from PDF images."""
        try:
            hotel_prompt = """You are a precise hotel booking extraction expert. Carefully read ALL PAGES of this hotel booking confirmation.

INSTRUCTIONS:
1. Extract hotel name EXACTLY as it appears
2. Extract full address including city
3. For dates, convert to YYYY-MM-DD format
4. For times, use HH:MM format
5. Calculate nights: check-out date - check-in date
6. Look for confirmation/booking reference number
7. Extract total cost and currency
8. Check all pages for complete information

Extract the following and return ONLY a valid JSON object (no markdown, no explanation):

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
}

CRITICAL:
- Use null for any field not found in the document
- nights = number of nights stayed (check-out date - check-in date)
- total_cost = final amount for the entire booking
- Do not use bold formatting or include reasoning"""

            contents = [hotel_prompt] + images
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents
            )

            if response.text:
                try:
                    print(f"Raw hotel response: {response.text[:500]}")
                    extracted_data = self._extract_json_from_response(response.text)
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.8
                    }
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {str(e)}")
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text[:500]
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Hotel extraction error: {str(e)}"}

    async def _extract_flight_from_pdf(self, uploaded_file) -> dict:
        """Extract ALL flight details from PDF using Gemini (including return flights)."""
        try:
            flight_prompt = """You are a precise data extraction expert. Carefully read ALL PAGES of this flight document (boarding pass, e-ticket, or flight confirmation).

INSTRUCTIONS:
1. Extract EXACT text as it appears - do not paraphrase or abbreviate
2. For dates, convert to YYYY-MM-DD format
3. For times, use 24-hour HH:MM format
4. IMPORTANT: If this is a ROUND-TRIP ticket, extract BOTH the outbound AND return flights
5. For multi-city trips, extract ALL flight segments
6. Check header, footer, and all sections of ALL pages
7. Each flight should be a separate object in the flights array

Extract ALL flights and return ONLY a valid JSON object (no markdown, no explanation):

{
    "flights": [
        {
            "airline": "full airline name exactly as shown",
            "flight_number": "flight code with letters and numbers (e.g., AA123, DL4567)",
            "departure_city": "full departure city name",
            "departure_airport": "3-letter IATA code (e.g., LAX, JFK)",
            "departure_terminal": "departure terminal (e.g., Terminal 1, Terminal A, T2)",
            "arrival_city": "full arrival city name",
            "arrival_airport": "3-letter IATA code",
            "arrival_terminal": "arrival terminal (e.g., Terminal 3, Terminal B, T4)",
            "departure_date": "YYYY-MM-DD format",
            "departure_time": "HH:MM in 24-hour format",
            "arrival_date": "YYYY-MM-DD format",
            "arrival_time": "HH:MM in 24-hour format",
            "gate": "gate number/letter if available",
            "seat": "seat assignment (e.g., 12A, 23F)",
            "booking_reference": "PNR/confirmation code (usually 6 characters)",
            "passenger_name": "passenger full name",
            "class": "cabin class (Economy, Business, First, etc.)"
        }
    ]
}

CRITICAL:
- For one-way tickets: flights array will have 1 object
- For round-trip tickets: flights array will have 2 objects (outbound first, return second)
- For multi-city: flights array will have multiple objects in chronological order
- Use null for any field not found in the document
- Booking reference is usually the SAME for all flights on the same reservation
- Do not use bold formatting or include reasoning"""

            response = self.model.generate_content([uploaded_file, flight_prompt])

            if response.text:
                try:
                    print(f"Raw flight response: {response.text[:500]}")
                    extracted_data = self._extract_json_from_response(response.text)
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.8
                    }
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {str(e)}")
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text[:500]
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Flight extraction error: {str(e)}"}

    async def _extract_receipt_from_pdf(self, uploaded_file) -> dict:
        """Extract receipt details from PDF using Gemini."""
        try:
            receipt_prompt = """You are a precise receipt data extraction expert. Carefully read ALL PAGES of this receipt/invoice document.

INSTRUCTIONS:
1. Extract merchant name EXACTLY as it appears (usually at top in large text)
2. Read ALL line items carefully - don't miss any
3. For prices, extract numeric values with 2 decimal places
4. Calculate subtotal by summing all item prices if not shown
5. CRITICAL: The TOTAL is the final amount paid - look for words like "Total", "Amount Due", "Balance", "Grand Total"
6. Check all pages for continuation of items or totals on subsequent pages
7. Distinguish between subtotal, tax, tip, and total carefully

Extract the following and return ONLY a valid JSON object (no markdown, no explanation):

{
    "merchant_name": "exact business name as shown",
    "location": "full address or at least city",
    "date": "YYYY-MM-DD format",
    "time": "HH:MM format (if available)",
    "items": [
        {"name": "exact item name", "price": 12.99, "quantity": 2}
    ],
    "subtotal": 0.00,
    "tax": 0.00,
    "tip": 0.00,
    "total": 0.00,
    "currency": "3-letter code like USD, EUR, GBP",
    "category": "classify as: food, transport, accommodation, entertainment, or shopping",
    "payment_method": "cash, card, or digital (if shown)"
}

IMPORTANT:
- If items list is long, include ALL items
- Ensure subtotal + tax + tip = total (approximately)
- Use null only if field truly doesn't exist
- Do not use bold formatting or include reasoning"""

            response = self.model.generate_content([uploaded_file, receipt_prompt])

            if response.text:
                try:
                    print(f"Raw receipt response: {response.text[:500]}")
                    extracted_data = self._extract_json_from_response(response.text)
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.85
                    }
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {str(e)}")
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text[:500]
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Receipt extraction error: {str(e)}"}

    async def _extract_hotel_from_pdf(self, uploaded_file) -> dict:
        """Extract hotel booking details from PDF using Gemini."""
        try:
            hotel_prompt = """You are a precise hotel booking data extraction expert. Carefully read ALL PAGES of this hotel booking confirmation or reservation document.

INSTRUCTIONS:
1. Extract hotel name EXACTLY as shown (look for property name, not chain name)
2. Check ALL pages - confirmations often span multiple pages
3. Calculate nights by counting days between check-in and check-out dates
4. Look for confirmation/reference numbers (usually alphanumeric codes)
5. Extract check-in and check-out times if specified (often 3:00 PM / 11:00 AM)
6. Total cost might be shown per night or total - extract the TOTAL for entire stay

Extract the following and return ONLY a valid JSON object (no markdown, no explanation):

{
    "hotel_name": "exact hotel/property name",
    "location": "full address or at least city and country",
    "check_in_date": "YYYY-MM-DD format",
    "check_in_time": "HH:MM format (default 15:00 if not specified)",
    "check_out_date": "YYYY-MM-DD format",
    "check_out_time": "HH:MM format (default 11:00 if not specified)",
    "nights": 0,
    "room_type": "room category/type (e.g., Deluxe King, Standard Double)",
    "guests": 0,
    "booking_reference": "confirmation/reservation number",
    "total_cost": 0.00,
    "currency": "3-letter code like USD, EUR, GBP",
    "guest_name": "primary guest name"
}

IMPORTANT:
- Nights = check_out_date minus check_in_date
- Look for total amount carefully - might be labeled as "Total Charges", "Amount Due", "Grand Total"
- Use null only if field truly doesn't exist
- Do not use bold formatting or include reasoning"""

            response = self.model.generate_content([uploaded_file, hotel_prompt])

            if response.text:
                try:
                    print(f"Raw hotel response: {response.text[:500]}")
                    extracted_data = self._extract_json_from_response(response.text)
                    return {
                        "success": True,
                        "data": extracted_data,
                        "confidence": 0.8
                    }
                except json.JSONDecodeError as e:
                    print(f"JSON parse error: {str(e)}")
                    return {
                        "success": False,
                        "error": "Could not parse AI response as JSON",
                        "raw_response": response.text[:500]
                    }
            else:
                return {"success": False, "error": "No response from AI"}

        except Exception as e:
            return {"success": False, "error": f"Hotel extraction error: {str(e)}"}

    async def process_document(self, image_data: bytes, document_type: str = None) -> dict:
        """
        Process document based on type or auto-classify.

        Args:
            image_data: Document image bytes
            document_type: Optional pre-classified type

        Returns:
            dict: Extraction result with document_type and extracted data
        """
        try:
            # Auto-classify if type not provided
            if not document_type:
                classification_result = await self.classify_document(image_data)
                if not classification_result.get("success"):
                    return classification_result
                document_type = classification_result["document_type"]

            # Route to appropriate extraction method
            if document_type == "flight_ticket":
                result = await self.extract_flight_details(image_data)
            elif document_type == "receipt":
                result = await self.extract_receipt_details(image_data)
            elif document_type == "hotel_booking":
                result = await self.extract_hotel_details(image_data)
            else:
                # Generic document (no structured extraction)
                result = {
                    "success": True,
                    "data": {},
                    "confidence": 0.5
                }

            # Add document_type to result
            if result.get("success"):
                result["document_type"] = document_type

            return result

        except Exception as e:
            return {"success": False, "error": f"Document processing error: {str(e)}"}

    async def classify_message_intent(self, text: str) -> str:
        """
        Classify user message intent for conversational detection.

        Args:
            text: User message text

        Returns:
            str: One of: itinerary_paste, place_mention, google_maps_url, question, other
        """
        if not self.available:
            return "other"

        try:
            # Quick URL check for Google Maps links
            if 'maps.google.com' in text or 'maps.app.goo.gl' in text or 'goo.gl/maps' in text:
                return "google_maps_url"

            # AI classification for text
            prompt = f"""Classify this user message into ONE category:

Message: "{text}"

Categories:
1. itinerary_paste - User is sharing their trip schedule/itinerary with dates and activities
2. place_mention - User mentions wanting to visit/try a specific restaurant or place
3. question - User is asking a question
4. other - Anything else

Respond with ONLY the category name, nothing else. Do not use bold formatting or include reasoning."""

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            intent = response.text.strip().lower()

            # Validate response
            valid_intents = ['itinerary_paste', 'place_mention', 'question', 'other']
            if intent in valid_intents:
                return intent
            else:
                return "other"

        except Exception as e:
            print(f"Error classifying intent: {e}")
            return "other"

    async def extract_itinerary_from_text(self, text: str, trip_start_date: str = None) -> dict:
        """
        Extract structured itinerary data from pasted schedule text.

        Args:
            text: User's pasted itinerary text
            trip_start_date: Optional trip start date for relative date calculation (YYYY-MM-DD)

        Returns:
            dict: {
                "success": bool,
                "items": [{"date": str, "time": str, "title": str, "description": str,
                          "location": str, "category": str, "day_order": int, "time_order": int}],
                "summary": str
            }
        """
        if not self.available:
            return {"success": False, "error": "Gemini not available"}

        try:
            context = f"Trip start date: {trip_start_date}" if trip_start_date else "No trip start date provided"

            prompt = f"""Extract itinerary information from this text and return ONLY valid JSON.

{context}

Text:
{text}

Extract each activity/event with:
- date (YYYY-MM-DD format, or null if unclear)
- time (HH:MM format in 24h, or null if unclear)
- title (brief activity name)
- description (optional details)
- location (place name if mentioned)
- category (one of: activity, dining, transport, other)
- day_order (which day of the trip: 1, 2, 3, etc.)
- time_order (order within that day: 1, 2, 3, etc.)

Also provide a human-readable summary.

Return JSON in this exact format:
{{
    "items": [
        {{
            "date": "2024-03-15",
            "time": "09:00",
            "title": "Visit Tsukiji Market",
            "description": "Fresh sushi breakfast",
            "location": "Tsukiji",
            "category": "activity",
            "day_order": 1,
            "time_order": 1
        }}
    ],
    "summary": "Day 1: Morning visit to Tsukiji Market..."
}}

Do not use bold formatting or include reasoning.

JSON:"""

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            result_json = self._extract_json_from_response(response.text)

            if not result_json.get("items"):
                return {"success": False, "error": "No itinerary items found"}

            return {
                "success": True,
                "items": result_json.get("items", []),
                "summary": result_json.get("summary", "Itinerary extracted")
            }

        except Exception as e:
            print(f"Error extracting itinerary: {e}")
            return {"success": False, "error": str(e)}

    async def extract_place_from_text(self, text: str) -> dict:
        """
        Extract place information from casual mention.

        Args:
            text: User message mentioning a place (e.g., "I want to try Sukiyabashi Jiro")

        Returns:
            dict: {
                "success": bool,
                "name": str,
                "suggested_category": str (restaurant, attraction, shopping, nightlife, other),
                "notes": str
            }
        """
        if not self.available:
            return {"success": False, "error": "Gemini not available"}

        try:
            prompt = f"""Extract place information from this message and return ONLY valid JSON.

Message: "{text}"

Extract:
- name: The place name mentioned
- suggested_category: Best category (restaurant, attraction, shopping, nightlife, other)
- notes: Any additional context from the message

Return JSON in this exact format:
{{
    "name": "Place Name",
    "suggested_category": "restaurant",
    "notes": "Any context from user message"
}}

Do not use bold formatting or include reasoning.

JSON:"""

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            result_json = self._extract_json_from_response(response.text)

            if not result_json.get("name"):
                return {"success": False, "error": "No place name found"}

            return {
                "success": True,
                "name": result_json.get("name"),
                "suggested_category": result_json.get("suggested_category", "other"),
                "notes": result_json.get("notes", "")
            }

        except Exception as e:
            print(f"Error extracting place: {e}")
            return {"success": False, "error": str(e)}

    async def generate_response_with_search(self, prompt: str,
                                           system_instruction: str = None) -> dict:
        """
        Generate AI response with Google Search grounding for real-time information.

        Args:
            prompt: User question/prompt
            system_instruction: Optional system instruction

        Returns:
            dict: {
                "response": str,
                "search_queries": list (if available),
                "grounding_metadata": dict (if available)
            }
        """
        if not self.available:
            return {"response": "AI service not available", "search_queries": [], "grounding_metadata": {}}

        try:
            # Generate with search grounding
            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{prompt}"
            else:
                full_prompt = prompt

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                )
            )

            # Extract grounding metadata if available
            grounding_metadata = {}
            search_queries = []

            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'grounding_metadata'):
                    grounding_metadata = candidate.grounding_metadata
                    if hasattr(grounding_metadata, 'search_entry_point'):
                        search_queries = getattr(grounding_metadata.search_entry_point, 'rendered_content', [])

            return {
                "response": response.text,
                "search_queries": search_queries,
                "grounding_metadata": grounding_metadata
            }

        except Exception as e:
            print(f"Error generating response with search: {e}")
            # Fallback to regular generation
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                return {
                    "response": response.text,
                    "search_queries": [],
                    "grounding_metadata": {}
                }
            except:
                return {
                    "response": f"Error: {str(e)}",
                    "search_queries": [],
                    "grounding_metadata": {}
                }

    async def call_function(self, prompt: str, tools: list,
                           system_instruction: str = None) -> dict:
        """
        Call Gemini with native function calling.

        Args:
            prompt: User message
            tools: List of function declarations (old JSON schema format)
            system_instruction: Optional context

        Returns:
            dict: {
                "type": "function_call" | "text_response",
                "function_name": str (if function_call),
                "arguments": dict (if function_call),
                "text": str (if text_response)
            }
        """
        if not self.available:
            return {"type": "text_response", "text": "AI service unavailable"}

        try:
            # Build prompt with system instruction
            full_prompt = prompt
            if system_instruction:
                full_prompt = f"{system_instruction}\n\nUser: {prompt}"

            # Convert old tool format to new google-genai format
            function_declarations = []
            for tool in tools:
                function_declarations.append(
                    types.FunctionDeclaration(
                        name=tool["name"],
                        description=tool["description"],
                        parameters=tool["parameters"]
                    )
                )

            # Create Tool with function declarations
            sdk_tools = [types.Tool(function_declarations=function_declarations)]

            # Generate with function calling
            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
                config=types.GenerateContentConfig(tools=sdk_tools)
            )

            # Parse response
            if response.candidates and response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]

                # Function call
                if hasattr(part, 'function_call'):
                    function_call = part.function_call
                    return {
                        "type": "function_call",
                        "function_name": function_call.name,
                        "arguments": dict(function_call.args)
                    }

                # Text response
                if hasattr(part, 'text'):
                    return {"type": "text_response", "text": part.text}

            # Fallback
            return {
                "type": "text_response",
                "text": response.text if response.text else "No response"
            }

        except Exception as e:
            print(f"Error in function calling: {e}")
            return {"type": "text_response", "text": f"Error: {str(e)}"}
