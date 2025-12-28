"""Gemini AI service for OCR and text generation."""
import os
import json
from PIL import Image
import io

try:
    import google.generativeai as genai
    DEPENDENCIES_AVAILABLE = True
except ImportError:
    DEPENDENCIES_AVAILABLE = False


class GeminiService:
    """Gemini AI service for document processing and Q&A."""

    def __init__(self):
        """Initialize Gemini with API key from environment."""
        if DEPENDENCIES_AVAILABLE:
            api_key = os.getenv('GOOGLE_GEMINI_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-2.5-flash')
                self.available = True
            else:
                self.available = False
                print("Warning: GOOGLE_GEMINI_API_KEY not found")
        else:
            self.available = False
            print("Warning: google-generativeai package not available")

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

            response = self.model.generate_content(full_prompt)
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
}"""

            response = self.model.generate_content([receipt_prompt, image])

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
}"""

            response = self.model.generate_content([hotel_prompt, image])

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
        Process PDF document using Gemini with inline data.

        Args:
            pdf_data: PDF file bytes
            document_type: Optional pre-classified type

        Returns:
            dict: Extraction result with document_type and extracted data
        """
        if not self.available:
            return {"success": False, "error": "AI service not available"}

        try:
            print(f"Processing PDF: {len(pdf_data)} bytes")

            # Validate PDF data
            if not pdf_data:
                return {"success": False, "error": "Empty PDF data received"}

            if len(pdf_data) < 100:
                return {"success": False, "error": f"PDF data too small: {len(pdf_data)} bytes"}

            # Encode PDF to base64 for inline data
            import base64
            pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

            # Create inline data part for Gemini
            pdf_part = {
                "mime_type": "application/pdf",
                "data": pdf_base64
            }

            # Classify document type if not provided
            if not document_type:
                classification_prompt = """Look at this PDF and classify it as one of these document types:
- flight_ticket: Airline boarding passes, flight confirmations, e-tickets
- receipt: Restaurant bills, shopping receipts, purchase invoices
- hotel_booking: Hotel confirmations, accommodation bookings
- itinerary: Travel schedules, trip plans, tour bookings
- other_document: Any other travel-related document

Return only the classification type, nothing else."""

                response = self.model.generate_content([classification_prompt, pdf_part])
                classification = response.text.strip().lower() if response.text else "other_document"

                # Validate classification
                valid_types = ["flight_ticket", "receipt", "hotel_booking", "itinerary", "other_document"]
                if classification not in valid_types:
                    classification = "other_document"

                document_type = classification

            # Extract data based on document type
            if document_type == "flight_ticket":
                result = await self._extract_flight_from_pdf(pdf_part)
            elif document_type == "receipt":
                result = await self._extract_receipt_from_pdf(pdf_part)
            elif document_type == "hotel_booking":
                result = await self._extract_hotel_from_pdf(pdf_part)
            else:
                # Generic document
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
            return {"success": False, "error": f"PDF processing error: {str(e)}"}

    async def _extract_flight_from_pdf(self, pdf_part) -> dict:
        """Extract flight details from PDF using Gemini."""
        try:
            flight_prompt = """Analyze this flight ticket/e-ticket PDF and extract the following information.
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

            response = self.model.generate_content([flight_prompt, pdf_part])

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

    async def _extract_receipt_from_pdf(self, pdf_part) -> dict:
        """Extract receipt details from PDF using Gemini."""
        try:
            receipt_prompt = """Analyze this receipt PDF and extract the following information.
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

            response = self.model.generate_content([receipt_prompt, pdf_part])

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

    async def _extract_hotel_from_pdf(self, pdf_part) -> dict:
        """Extract hotel booking details from PDF using Gemini."""
        try:
            hotel_prompt = """Analyze this hotel booking confirmation PDF and extract the following information.
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

            response = self.model.generate_content([hotel_prompt, pdf_part])

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
