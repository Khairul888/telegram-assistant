"""
Image processing service with OCR capabilities using Google Gemini Vision.
"""

import asyncio
import aiofiles
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import mimetypes

from PIL import Image, ImageEnhance, ImageFilter
import io
import base64

from ..core.config import settings
from ..core.logger import get_logger
from ..core.exceptions import TelegramAssistantException
from ..ai.gemini_service import gemini_service

logger = get_logger(__name__)


class ImageProcessingError(TelegramAssistantException):
    """Exception for image processing errors."""
    pass


class ImageProcessor:
    """Service for processing images and extracting text via OCR."""

    def __init__(self):
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff']
        self.max_size_mb = settings.max_file_size_mb
        self.max_dimension = 4096  # Max pixel dimension for processing

    def _validate_image(self, file_path: Path) -> Tuple[bool, str]:
        """
        Validate if the image file can be processed.

        Args:
            file_path: Path to image file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file exists
            if not file_path.exists():
                return False, "File does not exist"

            # Check file extension
            if file_path.suffix.lower() not in self.supported_formats:
                return False, f"Unsupported format. Supported: {', '.join(self.supported_formats)}"

            # Check file size
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_size_mb:
                return False, f"File too large ({file_size_mb:.1f}MB). Max: {self.max_size_mb}MB"

            # Try to open image
            with Image.open(file_path) as img:
                # Check dimensions
                if max(img.size) > self.max_dimension:
                    logger.warning(f"Image dimensions ({img.size}) exceed max ({self.max_dimension}). Will resize.")

                # Verify image is valid
                img.verify()

            return True, "Valid image"

        except Exception as e:
            return False, f"Invalid image file: {str(e)}"

    def _optimize_image_for_ocr(self, image: Image.Image) -> Image.Image:
        """
        Optimize image for better OCR results.

        Args:
            image: PIL Image object

        Returns:
            Optimized PIL Image
        """
        try:
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Resize if too large
            if max(image.size) > self.max_dimension:
                ratio = self.max_dimension / max(image.size)
                new_size = tuple(int(dim * ratio) for dim in image.size)
                image = image.resize(new_size, Image.Resampling.LANCZOS)
                logger.info(f"Resized image to {new_size}")

            # Enhance contrast for better OCR
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.2)

            # Sharpen slightly
            image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))

            return image

        except Exception as e:
            logger.error(f"Error optimizing image: {e}")
            return image

    async def _extract_text_with_gemini(self, image_path: Path) -> str:
        """
        Extract text from image using Google Gemini Vision API.

        Args:
            image_path: Path to image file

        Returns:
            Extracted text content
        """
        try:
            # Read image file
            async with aiofiles.open(image_path, 'rb') as f:
                image_data = await f.read()

            # Use existing Gemini service for text extraction
            extracted_text = await gemini_service.extract_text_from_image(
                image_data=image_data,
                filename=image_path.name
            )

            return extracted_text

        except Exception as e:
            logger.error(f"Error extracting text with Gemini: {e}")
            raise ImageProcessingError(f"OCR failed: {e}")

    async def _analyze_image_content(self, image_path: Path, extracted_text: str) -> Dict[str, Any]:
        """
        Analyze image content and extracted text for insights.

        Args:
            image_path: Path to image file
            extracted_text: OCR extracted text

        Returns:
            Analysis results dictionary
        """
        try:
            # If we have extracted text, analyze it
            if extracted_text and len(extracted_text.strip()) > 10:
                # Create analysis prompt
                analysis_prompt = f"""
Analyze this text that was extracted from an image file named "{image_path.name}":

{extracted_text}

Please provide:
1. Document type classification (receipt, business card, document, sign, etc.)
2. Key information extracted (3-5 bullet points)
3. Confidence level of OCR accuracy (1-10)
4. Summary of content (1-2 sentences)

Format as JSON:
{{
    "document_type": "classification",
    "key_information": ["point1", "point2", "point3"],
    "ocr_confidence": 8,
    "summary": "Brief summary",
    "has_structured_data": true/false
}}
"""

                analysis_response = await gemini_service.generate_response(
                    prompt=analysis_prompt,
                    temperature=0.3,
                    system_instruction="You are an expert at analyzing OCR text from images. Provide accurate and structured analysis."
                )

                # Try to parse JSON response
                try:
                    import json
                    analysis = json.loads(analysis_response)
                    return analysis
                except json.JSONDecodeError:
                    # Fallback if JSON parsing fails
                    return {
                        "document_type": "unknown",
                        "key_information": [extracted_text[:100] + "..." if len(extracted_text) > 100 else extracted_text],
                        "ocr_confidence": 5,
                        "summary": "Text extracted from image",
                        "has_structured_data": False
                    }
            else:
                # No meaningful text extracted
                return {
                    "document_type": "image",
                    "key_information": ["Image with minimal or no text content"],
                    "ocr_confidence": 1,
                    "summary": "Image processed but no significant text found",
                    "has_structured_data": False
                }

        except Exception as e:
            logger.error(f"Error analyzing image content: {e}")
            return {
                "document_type": "error",
                "key_information": [],
                "ocr_confidence": 0,
                "summary": f"Analysis failed: {str(e)}",
                "has_structured_data": False
            }

    async def process_image(self, file_path: Path) -> Dict[str, Any]:
        """
        Process an image file completely: validation, OCR, and analysis.

        Args:
            file_path: Path to image file

        Returns:
            Complete processing results
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting image processing for: {file_path.name}")

            # Validate image
            is_valid, validation_message = self._validate_image(file_path)
            if not is_valid:
                raise ImageProcessingError(validation_message)

            # Get image metadata
            with Image.open(file_path) as img:
                image_metadata = {
                    'format': img.format,
                    'mode': img.mode,
                    'size': img.size,
                    'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                }

            # Extract text using Gemini Vision
            logger.info("Extracting text using Gemini Vision API")
            extracted_text = await self._extract_text_with_gemini(file_path)

            # Analyze content
            logger.info("Analyzing extracted content")
            content_analysis = await self._analyze_image_content(file_path, extracted_text)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            # Compile results
            results = {
                'success': True,
                'file_name': file_path.name,
                'file_size_mb': file_path.stat().st_size / (1024 * 1024),
                'processing_time_seconds': processing_time,
                'image_metadata': image_metadata,
                'extracted_text': extracted_text,
                'text_length': len(extracted_text) if extracted_text else 0,
                'content_analysis': content_analysis,
                'processor': 'image_processor',
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Successfully processed image {file_path.name} in {processing_time:.2f}s")
            return results

        except ImageProcessingError:
            raise
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Unexpected error processing image {file_path.name}: {e}")

            return {
                'success': False,
                'file_name': file_path.name,
                'processing_time_seconds': processing_time,
                'error': str(e),
                'processor': 'image_processor',
                'timestamp': datetime.now().isoformat()
            }

    async def extract_text_only(self, file_path: Path) -> str:
        """
        Extract only text from image (simplified interface).

        Args:
            file_path: Path to image file

        Returns:
            Extracted text
        """
        try:
            # Validate image
            is_valid, validation_message = self._validate_image(file_path)
            if not is_valid:
                raise ImageProcessingError(validation_message)

            # Extract text
            extracted_text = await self._extract_text_with_gemini(file_path)
            return extracted_text if extracted_text else ""

        except Exception as e:
            logger.error(f"Error extracting text from {file_path.name}: {e}")
            return ""

    async def get_image_info(self, file_path: Path) -> Dict[str, Any]:
        """
        Get basic information about an image file.

        Args:
            file_path: Path to image file

        Returns:
            Image information dictionary
        """
        try:
            if not file_path.exists():
                raise ImageProcessingError("File does not exist")

            # Get file stats
            file_stats = file_path.stat()

            # Get image properties
            with Image.open(file_path) as img:
                return {
                    'file_name': file_path.name,
                    'file_size_bytes': file_stats.st_size,
                    'file_size_mb': file_stats.st_size / (1024 * 1024),
                    'format': img.format,
                    'mode': img.mode,
                    'width': img.size[0],
                    'height': img.size[1],
                    'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info,
                    'created_time': datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                    'modified_time': datetime.fromtimestamp(file_stats.st_mtime).isoformat()
                }

        except Exception as e:
            logger.error(f"Error getting image info for {file_path}: {e}")
            raise ImageProcessingError(f"Could not read image info: {e}")

    def is_supported_format(self, file_path: Path) -> bool:
        """
        Check if the file format is supported for image processing.

        Args:
            file_path: Path to file

        Returns:
            True if format is supported
        """
        return file_path.suffix.lower() in self.supported_formats

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the image processing service.

        Returns:
            Health status dictionary
        """
        try:
            # Check if Gemini service is available
            gemini_health = await gemini_service.health_check()

            return {
                'status': 'healthy' if gemini_health['status'] == 'healthy' else 'unhealthy',
                'supported_formats': self.supported_formats,
                'max_file_size_mb': self.max_size_mb,
                'max_dimension': self.max_dimension,
                'gemini_service_status': gemini_health['status'],
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Image processor health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global instance
image_processor = ImageProcessor()


async def get_image_processor() -> ImageProcessor:
    """Dependency for getting image processor."""
    return image_processor