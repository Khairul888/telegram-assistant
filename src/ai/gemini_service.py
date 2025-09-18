"""
Google Gemini AI service for text generation and analysis.
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json

from ..core.config import settings
from ..core.logger import get_logger
from ..core.exceptions import TelegramAssistantException

logger = get_logger(__name__)


class GeminiAPIError(TelegramAssistantException):
    """Exception for Gemini API errors."""
    pass


class GeminiService:
    """Service for interacting with Google Gemini API."""

    def __init__(self):
        self.api_key = settings.google_gemini_api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models"
        self.model_name = "gemini-1.5-flash"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        method: str = "POST"
    ) -> Dict[str, Any]:
        """Make API request to Gemini."""
        url = f"{self.base_url}/{endpoint}?key={self.api_key}"
        session = await self._get_session()

        try:
            async with session.request(method, url, json=data) as response:
                result = await response.json()

                if response.status != 200:
                    error_msg = result.get("error", {}).get("message", "Unknown Gemini API error")
                    logger.error(f"Gemini API error: {error_msg}", extra={
                        "status_code": response.status,
                        "endpoint": endpoint,
                        "error": result.get("error", {})
                    })
                    raise GeminiAPIError(f"Gemini API error ({response.status}): {error_msg}")

                return result

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error calling Gemini API: {e}", extra={
                "endpoint": endpoint,
                "method": method
            })
            raise GeminiAPIError(f"HTTP error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Gemini API: {e}")
            raise GeminiAPIError(f"Invalid JSON response: {e}")

    async def generate_response(
        self,
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_instruction: Optional[str] = None
    ) -> str:
        """Generate text response using Gemini."""
        try:
            # Use settings defaults if not provided
            max_tokens = max_tokens or settings.max_tokens_per_request
            temperature = temperature or settings.ai_temperature

            # Build the request
            data = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    "topP": 0.95,
                    "topK": 64
                },
                "safetySettings": [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
                    }
                ]
            }

            # Add system instruction if provided
            if system_instruction:
                data["systemInstruction"] = {
                    "parts": [{"text": system_instruction}]
                }

            logger.info("Generating Gemini response", extra={
                "prompt_length": len(prompt),
                "temperature": temperature,
                "max_tokens": max_tokens
            })

            # Make the request
            result = await self._make_request(f"{self.model_name}:generateContent", data)

            # Extract response text
            candidates = result.get("candidates", [])
            if not candidates:
                logger.warning("No candidates returned from Gemini")
                return "I'm unable to generate a response right now. Please try again."

            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", [])

            if not parts:
                logger.warning("No parts in Gemini response")
                return "I'm unable to generate a response right now. Please try again."

            response_text = parts[0].get("text", "")

            if not response_text:
                logger.warning("Empty response from Gemini")
                return "I'm unable to generate a response right now. Please try again."

            logger.info("Successfully generated Gemini response", extra={
                "response_length": len(response_text)
            })

            return response_text.strip()

        except GeminiAPIError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in Gemini response generation: {e}")
            raise GeminiAPIError(f"Unexpected error: {e}")

    async def analyze_document(
        self,
        text: str,
        document_type: str = "document"
    ) -> Dict[str, Any]:
        """Analyze document content and extract insights."""
        try:
            analysis_prompt = f"""
Analyze the following {document_type} and provide:

1. A concise summary (2-3 sentences)
2. Key topics and themes (list of 5-8 keywords)
3. Main insights or conclusions
4. Document type classification
5. Estimated reading difficulty (beginner/intermediate/advanced)

Document content:
{text[:8000]}  # Limit to avoid token limits

Please format your response as JSON with the following structure:
{{
    "summary": "Brief summary here",
    "keywords": ["keyword1", "keyword2", ...],
    "insights": ["insight1", "insight2", ...],
    "document_type": "classification",
    "difficulty": "level",
    "confidence": 0.95
}}
"""

            response = await self.generate_response(
                prompt=analysis_prompt,
                temperature=0.3,  # Lower temperature for more consistent analysis
                system_instruction="You are a document analysis expert. Provide accurate and concise analysis."
            )

            # Try to parse JSON response
            try:
                analysis = json.loads(response)
                return analysis
            except json.JSONDecodeError:
                # If JSON parsing fails, extract information manually
                return {
                    "summary": response[:500],
                    "keywords": [],
                    "insights": [],
                    "document_type": document_type,
                    "difficulty": "unknown",
                    "confidence": 0.5
                }

        except Exception as e:
            logger.error(f"Error analyzing document: {e}")
            return {
                "summary": "Analysis failed",
                "keywords": [],
                "insights": [],
                "document_type": document_type,
                "difficulty": "unknown",
                "confidence": 0.0
            }

    async def extract_text_from_image(self, image_data: bytes, filename: str) -> str:
        """Extract text from image using Gemini Vision."""
        try:
            import base64

            # Convert image to base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')

            # Determine MIME type
            mime_type = "image/jpeg"
            if filename.lower().endswith(('.png',)):
                mime_type = "image/png"
            elif filename.lower().endswith(('.gif',)):
                mime_type = "image/gif"
            elif filename.lower().endswith(('.webp',)):
                mime_type = "image/webp"

            data = {
                "contents": [
                    {
                        "parts": [
                            {"text": "Extract all text from this image. If there's no text, describe what you see."},
                            {
                                "inline_data": {
                                    "mime_type": mime_type,
                                    "data": image_b64
                                }
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 2048
                }
            }

            logger.info("Extracting text from image", extra={
                "filename": filename,
                "mime_type": mime_type,
                "image_size": len(image_data)
            })

            result = await self._make_request(f"{self.model_name}:generateContent", data)

            # Extract response
            candidates = result.get("candidates", [])
            if candidates:
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    extracted_text = parts[0].get("text", "")
                    return extracted_text.strip()

            return "No text could be extracted from the image."

        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            return f"Error extracting text: {str(e)}"

    async def generate_embeddings(self, text: str) -> List[float]:
        """Generate embeddings for text (if supported by model)."""
        # Note: Gemini might not have a direct embedding endpoint
        # This is a placeholder for when embedding functionality is available
        try:
            # For now, we'll use a simple text hash as a placeholder
            # In production, you'd use a proper embedding model
            import hashlib
            text_hash = hashlib.md5(text.encode()).hexdigest()
            # Convert to simple float vector for compatibility
            return [float(int(text_hash[i:i+2], 16)) / 255.0 for i in range(0, len(text_hash), 2)]

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return []

    async def summarize_conversation(self, messages: List[Dict[str, str]]) -> str:
        """Summarize a conversation history."""
        try:
            # Build conversation text
            conversation_text = ""
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation_text += f"{role.title()}: {content}\n"

            summary_prompt = f"""
Summarize the following conversation in 2-3 sentences, highlighting the main topics discussed and any conclusions reached:

{conversation_text}
"""

            summary = await self.generate_response(
                prompt=summary_prompt,
                temperature=0.3,
                system_instruction="You are a conversation summarization expert. Provide concise and accurate summaries."
            )

            return summary

        except Exception as e:
            logger.error(f"Error summarizing conversation: {e}")
            return "Unable to summarize conversation."

    async def health_check(self) -> Dict[str, Any]:
        """Check if Gemini API is accessible."""
        try:
            # Make a simple test request
            test_response = await self.generate_response(
                "Say 'API is working' if you can read this message.",
                max_tokens=10,
                temperature=0.1
            )

            is_healthy = "working" in test_response.lower()

            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "model": self.model_name,
                "response": test_response,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global instance
gemini_service = GeminiService()


async def get_gemini_service() -> GeminiService:
    """Dependency for getting Gemini service."""
    return gemini_service