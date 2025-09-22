"""
Text processing service for DOCX, PDF, and plain text files.
"""

import asyncio
import aiofiles
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
import json
import re

from docx import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

import PyPDF2
import io

from ..core.config import settings
from ..core.logger import get_logger
from ..core.exceptions import TelegramAssistantException
from ..ai.gemini_service import gemini_service

logger = get_logger(__name__)


class TextProcessingError(TelegramAssistantException):
    """Exception for text processing errors."""
    pass


class TextProcessor:
    """Service for processing text documents (DOCX, PDF, TXT)."""

    def __init__(self):
        self.supported_formats = ['.docx', '.pdf', '.txt', '.rtf', '.md']
        self.max_size_mb = settings.max_file_size_mb
        self.max_chars = 500000  # Limit for very large documents

    def _validate_file(self, file_path: Path) -> Tuple[bool, str]:
        """
        Validate if the file can be processed.

        Args:
            file_path: Path to file

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

            return True, "Valid file"

        except Exception as e:
            return False, f"Invalid file: {str(e)}"

    async def _extract_docx_content(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract content from DOCX file with structure preservation.

        Args:
            file_path: Path to DOCX file

        Returns:
            Dictionary with extracted content and metadata
        """
        try:
            doc = Document(file_path)

            # Extract text content
            paragraphs = []
            tables = []
            headers = []

            # Process document elements in order
            for element in doc.element.body:
                if isinstance(element, CT_P):
                    # Paragraph
                    paragraph = Paragraph(element, doc)
                    text = paragraph.text.strip()
                    if text:
                        # Check if it's likely a header
                        if paragraph.style.name.startswith('Heading') or len(text) < 100:
                            headers.append(text)
                        paragraphs.append(text)

                elif isinstance(element, CT_Tbl):
                    # Table
                    table = Table(element, doc)
                    table_data = []

                    for row in table.rows:
                        row_data = []
                        for cell in row.cells:
                            cell_text = cell.text.strip()
                            row_data.append(cell_text)
                        if any(row_data):  # Only add non-empty rows
                            table_data.append(row_data)

                    if table_data:
                        tables.append(table_data)

            # Combine all text
            full_text = '\n'.join(paragraphs)

            # Extract metadata
            core_props = doc.core_properties
            metadata = {
                'title': core_props.title or '',
                'author': core_props.author or '',
                'subject': core_props.subject or '',
                'created': core_props.created.isoformat() if core_props.created else None,
                'modified': core_props.modified.isoformat() if core_props.modified else None,
                'keywords': core_props.keywords or '',
                'comments': core_props.comments or ''
            }

            # Document statistics
            word_count = len(full_text.split())
            char_count = len(full_text)
            paragraph_count = len([p for p in paragraphs if p.strip()])

            return {
                'full_text': full_text,
                'paragraphs': paragraphs,
                'headers': headers,
                'tables': tables,
                'metadata': metadata,
                'statistics': {
                    'word_count': word_count,
                    'character_count': char_count,
                    'paragraph_count': paragraph_count,
                    'table_count': len(tables),
                    'header_count': len(headers)
                }
            }

        except Exception as e:
            logger.error(f"Error extracting DOCX content: {e}")
            raise TextProcessingError(f"Failed to extract DOCX content: {e}")

    async def _extract_pdf_content(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract content from PDF file.

        Args:
            file_path: Path to PDF file

        Returns:
            Dictionary with extracted content and metadata
        """
        try:
            text_content = []
            metadata = {}

            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                # Extract metadata
                if pdf_reader.metadata:
                    metadata = {
                        'title': pdf_reader.metadata.get('/Title', ''),
                        'author': pdf_reader.metadata.get('/Author', ''),
                        'subject': pdf_reader.metadata.get('/Subject', ''),
                        'creator': pdf_reader.metadata.get('/Creator', ''),
                        'producer': pdf_reader.metadata.get('/Producer', ''),
                        'creation_date': str(pdf_reader.metadata.get('/CreationDate', '')),
                        'modification_date': str(pdf_reader.metadata.get('/ModDate', ''))
                    }

                # Extract text from each page
                total_pages = len(pdf_reader.pages)
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text.strip():
                            text_content.append(f"--- Page {page_num + 1} ---\n{page_text}")
                    except Exception as page_error:
                        logger.warning(f"Error extracting text from page {page_num + 1}: {page_error}")
                        text_content.append(f"--- Page {page_num + 1} ---\n[Text extraction failed]")

            full_text = '\n\n'.join(text_content)
            word_count = len(full_text.split())
            char_count = len(full_text)

            return {
                'full_text': full_text,
                'pages': text_content,
                'metadata': metadata,
                'statistics': {
                    'word_count': word_count,
                    'character_count': char_count,
                    'page_count': total_pages
                }
            }

        except Exception as e:
            logger.error(f"Error extracting PDF content: {e}")
            raise TextProcessingError(f"Failed to extract PDF content: {e}")

    async def _extract_text_content(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract content from plain text files.

        Args:
            file_path: Path to text file

        Returns:
            Dictionary with extracted content and metadata
        """
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
            content = None

            for encoding in encodings:
                try:
                    async with aiofiles.open(file_path, 'r', encoding=encoding) as f:
                        content = await f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise TextProcessingError("Could not decode text file with any supported encoding")

            # Basic statistics
            lines = content.split('\n')
            paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
            word_count = len(content.split())
            char_count = len(content)

            return {
                'full_text': content,
                'lines': lines,
                'paragraphs': paragraphs,
                'metadata': {
                    'encoding': encoding,
                    'file_size': file_path.stat().st_size
                },
                'statistics': {
                    'word_count': word_count,
                    'character_count': char_count,
                    'line_count': len(lines),
                    'paragraph_count': len(paragraphs)
                }
            }

        except Exception as e:
            logger.error(f"Error extracting text content: {e}")
            raise TextProcessingError(f"Failed to extract text content: {e}")

    def _analyze_text_structure(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the structure and characteristics of extracted text.

        Args:
            content: Extracted content dictionary

        Returns:
            Analysis results
        """
        try:
            full_text = content['full_text']

            # Text characteristics
            sentences = re.split(r'[.!?]+', full_text)
            sentences = [s.strip() for s in sentences if s.strip()]

            # Reading level estimation (simple)
            avg_words_per_sentence = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0

            # Content type detection
            content_indicators = {
                'technical': len(re.findall(r'\b(?:API|SQL|HTTP|JSON|XML|CSS|HTML|JavaScript)\b', full_text, re.IGNORECASE)),
                'business': len(re.findall(r'\b(?:revenue|profit|budget|ROI|KPI|quarterly|annual)\b', full_text, re.IGNORECASE)),
                'academic': len(re.findall(r'\b(?:research|study|analysis|methodology|conclusion|abstract)\b', full_text, re.IGNORECASE)),
                'legal': len(re.findall(r'\b(?:agreement|contract|clause|liability|jurisdiction|hereby)\b', full_text, re.IGNORECASE)),
                'medical': len(re.findall(r'\b(?:patient|diagnosis|treatment|symptoms|medical|clinical)\b', full_text, re.IGNORECASE))
            }

            # Determine primary content type
            primary_type = max(content_indicators, key=content_indicators.get) if any(content_indicators.values()) else 'general'

            # Language complexity
            long_words = len([word for word in full_text.split() if len(word) > 7])
            total_words = len(full_text.split())
            complexity_ratio = long_words / total_words if total_words > 0 else 0

            return {
                'sentence_count': len(sentences),
                'avg_words_per_sentence': round(avg_words_per_sentence, 1),
                'content_type': primary_type,
                'content_indicators': content_indicators,
                'complexity_ratio': round(complexity_ratio, 3),
                'estimated_reading_time_minutes': round(total_words / 200, 1),  # Assuming 200 WPM
                'has_tables': 'tables' in content and len(content.get('tables', [])) > 0,
                'has_headers': 'headers' in content and len(content.get('headers', [])) > 0
            }

        except Exception as e:
            logger.error(f"Error analyzing text structure: {e}")
            return {
                'sentence_count': 0,
                'content_type': 'unknown',
                'error': str(e)
            }

    async def _generate_ai_summary(self, file_name: str, content: Dict[str, Any], structure_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate AI-powered summary and insights.

        Args:
            file_name: Name of the file
            content: Extracted content
            structure_analysis: Structure analysis results

        Returns:
            AI analysis results
        """
        try:
            # Prepare text for analysis (truncate if too long)
            full_text = content['full_text']
            if len(full_text) > 8000:
                full_text = full_text[:8000] + "\n\n[Content truncated for analysis...]"

            analysis_prompt = f"""
Analyze this document "{file_name}" and provide insights:

DOCUMENT CONTENT:
{full_text}

DOCUMENT STATS:
- Type: {structure_analysis.get('content_type', 'unknown')}
- Word count: {content.get('statistics', {}).get('word_count', 0)}
- Estimated reading time: {structure_analysis.get('estimated_reading_time_minutes', 0)} minutes
- Has tables: {structure_analysis.get('has_tables', False)}
- Has headers: {structure_analysis.get('has_headers', False)}

Please provide analysis as JSON:
{{
    "document_type": "report/article/manual/contract/etc",
    "main_topic": "primary subject matter",
    "key_points": ["point1", "point2", "point3"],
    "summary": "2-3 sentence summary",
    "target_audience": "who this is written for",
    "action_items": ["action1", "action2"],
    "sentiment": "positive/neutral/negative",
    "confidence_score": 0.85,
    "contains_sensitive_info": true/false
}}
"""

            ai_response = await gemini_service.generate_response(
                prompt=analysis_prompt,
                temperature=0.3,
                system_instruction="You are an expert document analyzer. Provide accurate and insightful analysis of text documents."
            )

            # Try to parse JSON response
            try:
                analysis = json.loads(ai_response)
                return analysis
            except json.JSONDecodeError:
                # Fallback if JSON parsing fails
                return {
                    "document_type": structure_analysis.get('content_type', 'unknown'),
                    "main_topic": "Document analysis",
                    "key_points": ["Document processed successfully"],
                    "summary": ai_response[:300] + "..." if len(ai_response) > 300 else ai_response,
                    "target_audience": "General",
                    "action_items": [],
                    "sentiment": "neutral",
                    "confidence_score": 0.5,
                    "contains_sensitive_info": False
                }

        except Exception as e:
            logger.error(f"Error generating AI summary: {e}")
            return {
                "document_type": "error",
                "main_topic": "Analysis failed",
                "key_points": [],
                "summary": f"AI analysis failed: {str(e)}",
                "target_audience": "Unknown",
                "action_items": [],
                "sentiment": "neutral",
                "confidence_score": 0.0,
                "contains_sensitive_info": False
            }

    async def process_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a text document file completely.

        Args:
            file_path: Path to file

        Returns:
            Complete processing results
        """
        start_time = datetime.now()

        try:
            logger.info(f"Starting text processing for: {file_path.name}")

            # Validate file
            is_valid, validation_message = self._validate_file(file_path)
            if not is_valid:
                raise TextProcessingError(validation_message)

            # Extract content based on file type
            file_ext = file_path.suffix.lower()

            if file_ext == '.docx':
                logger.info("Extracting DOCX content")
                content = await self._extract_docx_content(file_path)
            elif file_ext == '.pdf':
                logger.info("Extracting PDF content")
                content = await self._extract_pdf_content(file_path)
            else:
                logger.info("Extracting plain text content")
                content = await self._extract_text_content(file_path)

            # Analyze structure
            logger.info("Analyzing text structure")
            structure_analysis = self._analyze_text_structure(content)

            # Generate AI insights
            logger.info("Generating AI summary and insights")
            ai_insights = await self._generate_ai_summary(file_path.name, content, structure_analysis)

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            # Compile results
            results = {
                'success': True,
                'file_name': file_path.name,
                'file_size_mb': file_path.stat().st_size / (1024 * 1024),
                'processing_time_seconds': processing_time,
                'file_type': file_ext,
                'extracted_content': {
                    'full_text': content['full_text'][:2000] + "..." if len(content['full_text']) > 2000 else content['full_text'],  # Truncated for storage
                    'statistics': content.get('statistics', {}),
                    'metadata': content.get('metadata', {})
                },
                'full_text_length': len(content['full_text']),
                'structure_analysis': structure_analysis,
                'ai_insights': ai_insights,
                'processor': 'text_processor',
                'timestamp': datetime.now().isoformat()
            }

            # Add format-specific data
            if 'tables' in content and content['tables']:
                results['has_tables'] = True
                results['table_count'] = len(content['tables'])

            if 'headers' in content and content['headers']:
                results['headers'] = content['headers'][:10]  # Limit stored headers

            if 'pages' in content:
                results['page_count'] = len(content['pages'])

            logger.info(f"Successfully processed {file_path.name} ({content.get('statistics', {}).get('word_count', 0)} words) in {processing_time:.2f}s")
            return results

        except TextProcessingError:
            raise
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Unexpected error processing {file_path.name}: {e}")

            return {
                'success': False,
                'file_name': file_path.name,
                'processing_time_seconds': processing_time,
                'error': str(e),
                'processor': 'text_processor',
                'timestamp': datetime.now().isoformat()
            }

    async def extract_text_only(self, file_path: Path) -> str:
        """
        Extract only text content from file (simplified interface).

        Args:
            file_path: Path to file

        Returns:
            Extracted text content
        """
        try:
            # Validate file
            is_valid, validation_message = self._validate_file(file_path)
            if not is_valid:
                raise TextProcessingError(validation_message)

            # Extract based on file type
            file_ext = file_path.suffix.lower()

            if file_ext == '.docx':
                content = await self._extract_docx_content(file_path)
            elif file_ext == '.pdf':
                content = await self._extract_pdf_content(file_path)
            else:
                content = await self._extract_text_content(file_path)

            return content['full_text']

        except Exception as e:
            logger.error(f"Error extracting text from {file_path.name}: {e}")
            return ""

    def is_supported_format(self, file_path: Path) -> bool:
        """
        Check if the file format is supported.

        Args:
            file_path: Path to file

        Returns:
            True if format is supported
        """
        return file_path.suffix.lower() in self.supported_formats

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the text processing service.

        Returns:
            Health status dictionary
        """
        try:
            # Test basic functionality
            import docx
            import PyPDF2

            return {
                'status': 'healthy',
                'supported_formats': self.supported_formats,
                'max_file_size_mb': self.max_size_mb,
                'max_chars': self.max_chars,
                'docx_available': True,
                'pypdf2_available': True,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Text processor health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global instance
text_processor = TextProcessor()


async def get_text_processor() -> TextProcessor:
    """Dependency for getting text processor."""
    return text_processor