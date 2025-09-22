"""
Document ingestion workflow for processing files from Google Drive.
Integrates Drive monitoring, file processing, AI analysis, and vector storage.
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json

from ..core.config import settings
from ..core.logger import get_logger
from ..core.exceptions import TelegramAssistantException
from ..services.google_drive_service import google_drive_service
from ..services.telegram_service import telegram_service
from ..processors.image_processor import image_processor
from ..processors.excel_processor import excel_processor
from ..processors.text_processor import text_processor
from ..ai.gemini_service import gemini_service

logger = get_logger(__name__)


class DocumentIngestionError(TelegramAssistantException):
    """Exception for document ingestion workflow errors."""
    pass


class DocumentProcessor:
    """Unified document processor that routes files to appropriate processors."""

    def __init__(self):
        self.processors = {
            'image': image_processor,
            'excel': excel_processor,
            'text': text_processor
        }

    def _determine_processor(self, file_path: Path) -> Optional[str]:
        """
        Determine which processor to use for a file.

        Args:
            file_path: Path to file

        Returns:
            Processor type ('image', 'excel', 'text') or None if unsupported
        """
        extension = file_path.suffix.lower()

        # Image files
        if extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff']:
            return 'image'

        # Excel/CSV files
        elif extension in ['.xlsx', '.xls', '.csv', '.tsv']:
            return 'excel'

        # Text documents
        elif extension in ['.docx', '.pdf', '.txt', '.rtf', '.md']:
            return 'text'

        return None

    async def process_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a file using the appropriate processor.

        Args:
            file_path: Path to file

        Returns:
            Processing results
        """
        try:
            processor_type = self._determine_processor(file_path)

            if not processor_type:
                raise DocumentIngestionError(f"Unsupported file type: {file_path.suffix}")

            processor = self.processors[processor_type]
            logger.info(f"Processing {file_path.name} with {processor_type} processor")

            # Process the file
            results = await processor.process_file(file_path)

            # Add processor type to results
            results['processor_type'] = processor_type

            return results

        except Exception as e:
            logger.error(f"Error processing file {file_path.name}: {e}")
            raise DocumentIngestionError(f"Processing failed: {e}")


class DocumentIngestionWorkflow:
    """Main workflow for document ingestion from Google Drive to processed storage."""

    def __init__(self):
        self.drive_service = google_drive_service
        self.telegram_service = telegram_service
        self.document_processor = DocumentProcessor()
        self.processing_history = {}  # Simple in-memory tracking
        self.is_running = False

    async def process_single_file(self, drive_file: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single file from Google Drive.

        Args:
            drive_file: File metadata from Google Drive

        Returns:
            Complete processing results
        """
        file_id = drive_file['id']
        file_name = drive_file['name']
        processing_start = datetime.now()

        try:
            logger.info(f"Starting processing workflow for: {file_name}")

            # Step 1: Download file from Google Drive
            logger.info(f"Downloading {file_name} from Google Drive")
            local_file_path, file_metadata = await self.drive_service.download_file(file_id, file_name)

            # Step 2: Process file based on type
            logger.info(f"Processing {file_name}")
            processing_results = await self.document_processor.process_file(local_file_path)

            # Step 3: Generate embeddings for vector storage (if text available)
            logger.info("Generating embeddings for vector storage")
            embeddings_data = await self._generate_embeddings(processing_results)

            # Step 4: Store in vector database (placeholder for now)
            logger.info("Storing in vector database")
            vector_storage_results = await self._store_in_vector_db(processing_results, embeddings_data)

            # Step 5: Send Telegram notification
            logger.info("Sending Telegram notification")
            notification_sent = await self._send_processing_notification(drive_file, processing_results)

            # Step 6: Cleanup temporary files
            try:
                local_file_path.unlink()
                logger.info(f"Cleaned up temporary file: {local_file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup {local_file_path}: {cleanup_error}")

            # Compile final results
            workflow_results = {
                'success': True,
                'file_id': file_id,
                'file_name': file_name,
                'drive_metadata': file_metadata,
                'processing_results': processing_results,
                'embeddings_generated': embeddings_data['success'] if embeddings_data else False,
                'vector_storage_success': vector_storage_results['success'] if vector_storage_results else False,
                'notification_sent': notification_sent,
                'total_processing_time': (datetime.now() - processing_start).total_seconds(),
                'workflow_timestamp': datetime.now().isoformat()
            }

            # Update processing history
            self.processing_history[file_id] = {
                'file_name': file_name,
                'processed_at': datetime.now().isoformat(),
                'success': True,
                'processor_type': processing_results.get('processor_type')
            }

            logger.info(f"Successfully completed processing workflow for {file_name}")
            return workflow_results

        except Exception as e:
            logger.error(f"Processing workflow failed for {file_name}: {e}")

            # Send error notification
            try:
                await self._send_error_notification(drive_file, str(e))
            except Exception as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")

            # Update processing history with error
            self.processing_history[file_id] = {
                'file_name': file_name,
                'processed_at': datetime.now().isoformat(),
                'success': False,
                'error': str(e)
            }

            return {
                'success': False,
                'file_id': file_id,
                'file_name': file_name,
                'error': str(e),
                'total_processing_time': (datetime.now() - processing_start).total_seconds(),
                'workflow_timestamp': datetime.now().isoformat()
            }

    async def _generate_embeddings(self, processing_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate embeddings for vector storage.

        Args:
            processing_results: Results from document processing

        Returns:
            Embeddings generation results
        """
        try:
            # Extract text content based on processor type
            text_content = ""

            if processing_results.get('processor_type') == 'image':
                text_content = processing_results.get('extracted_text', '')

            elif processing_results.get('processor_type') == 'excel':
                text_content = processing_results.get('text_summary', '')

            elif processing_results.get('processor_type') == 'text':
                extracted_content = processing_results.get('extracted_content', {})
                text_content = extracted_content.get('full_text', '')

            if not text_content or len(text_content.strip()) < 50:
                return {
                    'success': False,
                    'reason': 'Insufficient text content for embeddings'
                }

            # For now, use a simple text representation
            # In production, you'd use a proper embedding model
            embeddings_summary = {
                'text_length': len(text_content),
                'text_preview': text_content[:500],
                'embedding_model': 'placeholder',
                'dimensions': 768,  # Standard embedding dimension
                'generated_at': datetime.now().isoformat()
            }

            return {
                'success': True,
                'embeddings_summary': embeddings_summary,
                'text_content': text_content[:1000]  # Store first 1000 chars
            }

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _store_in_vector_db(self, processing_results: Dict[str, Any], embeddings_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store processed document in vector database (placeholder implementation).

        Args:
            processing_results: Document processing results
            embeddings_data: Generated embeddings data

        Returns:
            Storage results
        """
        try:
            # Placeholder for Pinecone/vector database storage
            # In production, this would:
            # 1. Generate proper embeddings using sentence-transformers or similar
            # 2. Store in Pinecone with metadata
            # 3. Return storage confirmation

            storage_metadata = {
                'file_name': processing_results.get('file_name'),
                'processor_type': processing_results.get('processor_type'),
                'stored_at': datetime.now().isoformat(),
                'index_name': settings.pinecone_index_name,
                'vector_id': f"{processing_results.get('file_name')}_{int(datetime.now().timestamp())}"
            }

            logger.info(f"Vector storage placeholder executed for {processing_results.get('file_name')}")

            return {
                'success': True,
                'storage_metadata': storage_metadata,
                'message': 'Document prepared for vector storage (implementation pending)'
            }

        except Exception as e:
            logger.error(f"Error storing in vector database: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    async def _send_processing_notification(self, drive_file: Dict[str, Any], processing_results: Dict[str, Any]) -> bool:
        """
        Send Telegram notification about successful processing.

        Args:
            drive_file: Google Drive file metadata
            processing_results: Processing results

        Returns:
            True if notification sent successfully
        """
        try:
            file_name = drive_file['name']
            processor_type = processing_results.get('processor_type', 'unknown')
            success = processing_results.get('success', False)

            if success:
                # Create success message based on processor type
                if processor_type == 'image':
                    text_extracted = processing_results.get('extracted_text', '')
                    text_length = len(text_extracted) if text_extracted else 0
                    message = f"🖼️ **Image Processed Successfully**\n\n📄 **File:** {file_name}\n📝 **Text Extracted:** {text_length} characters\n✅ **Status:** Ready for queries"

                elif processor_type == 'excel':
                    sheets = processing_results.get('sheet_count', 0)
                    rows = processing_results.get('total_rows', 0)
                    message = f"📊 **Spreadsheet Processed Successfully**\n\n📄 **File:** {file_name}\n📋 **Sheets:** {sheets}\n📈 **Rows:** {rows}\n✅ **Status:** Ready for queries"

                elif processor_type == 'text':
                    word_count = processing_results.get('extracted_content', {}).get('statistics', {}).get('word_count', 0)
                    message = f"📄 **Document Processed Successfully**\n\n📄 **File:** {file_name}\n📝 **Words:** {word_count}\n✅ **Status:** Ready for queries"

                else:
                    message = f"✅ **File Processed Successfully**\n\n📄 **File:** {file_name}\n🔧 **Processor:** {processor_type}\n✅ **Status:** Ready for queries"

            else:
                error = processing_results.get('error', 'Unknown error')
                message = f"❌ **Processing Failed**\n\n📄 **File:** {file_name}\n⚠️ **Error:** {error}"

            # Send notification (placeholder - would use actual Telegram service)
            logger.info(f"Telegram notification: {message}")

            return True

        except Exception as e:
            logger.error(f"Error sending processing notification: {e}")
            return False

    async def _send_error_notification(self, drive_file: Dict[str, Any], error_message: str) -> bool:
        """
        Send Telegram notification about processing error.

        Args:
            drive_file: Google Drive file metadata
            error_message: Error description

        Returns:
            True if notification sent successfully
        """
        try:
            file_name = drive_file['name']
            message = f"❌ **Processing Error**\n\n📄 **File:** {file_name}\n⚠️ **Error:** {error_message}\n\n🔄 **Action:** File will be retried automatically"

            # Send error notification (placeholder)
            logger.warning(f"Error notification: {message}")

            return True

        except Exception as e:
            logger.error(f"Error sending error notification: {e}")
            return False

    async def process_new_files(self, since_minutes: int = 5) -> Dict[str, Any]:
        """
        Process all new files from Google Drive.

        Args:
            since_minutes: Look for files modified in the last N minutes

        Returns:
            Processing summary
        """
        try:
            logger.info(f"Checking for new files in the last {since_minutes} minutes")

            # Get new files from Google Drive
            new_files = await self.drive_service.get_new_files(since_minutes=since_minutes)

            if not new_files:
                logger.info("No new files found")
                return {
                    'files_found': 0,
                    'files_processed': 0,
                    'files_failed': 0,
                    'message': 'No new files to process'
                }

            logger.info(f"Found {len(new_files)} new files to process")

            # Process each file
            processed_successfully = 0
            processing_errors = 0
            processing_results = []

            for file_info in new_files:
                try:
                    # Skip if already processed recently
                    if file_info['id'] in self.processing_history:
                        last_processed = self.processing_history[file_info['id']]
                        if last_processed.get('success'):
                            logger.info(f"Skipping {file_info['name']} - already processed successfully")
                            continue

                    # Process the file
                    result = await self.process_single_file(file_info)
                    processing_results.append(result)

                    if result['success']:
                        processed_successfully += 1
                    else:
                        processing_errors += 1

                except Exception as file_error:
                    logger.error(f"Error processing file {file_info['name']}: {file_error}")
                    processing_errors += 1

            # Summary
            summary = {
                'files_found': len(new_files),
                'files_processed': processed_successfully,
                'files_failed': processing_errors,
                'processing_results': processing_results,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(f"Processing complete: {processed_successfully} success, {processing_errors} errors")
            return summary

        except Exception as e:
            logger.error(f"Error in process_new_files: {e}")
            raise DocumentIngestionError(f"Failed to process new files: {e}")

    async def start_monitoring(self, check_interval_minutes: int = 5):
        """
        Start continuous monitoring for new files.

        Args:
            check_interval_minutes: How often to check for new files
        """
        if self.is_running:
            logger.warning("Monitoring is already running")
            return

        self.is_running = True
        logger.info(f"Starting document monitoring (checking every {check_interval_minutes} minutes)")

        try:
            while self.is_running:
                try:
                    await self.process_new_files(since_minutes=check_interval_minutes + 1)
                except Exception as e:
                    logger.error(f"Error during monitoring cycle: {e}")

                # Wait for next check
                await asyncio.sleep(check_interval_minutes * 60)

        except asyncio.CancelledError:
            logger.info("Monitoring was cancelled")
        finally:
            self.is_running = False
            logger.info("Document monitoring stopped")

    def stop_monitoring(self):
        """Stop the monitoring process."""
        self.is_running = False
        logger.info("Stopping document monitoring")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the ingestion workflow.

        Returns:
            Health status
        """
        try:
            # Check individual components
            drive_health = await self.drive_service.health_check()
            image_health = await image_processor.health_check()
            excel_health = await excel_processor.health_check()
            text_health = await text_processor.health_check()
            gemini_health = await gemini_service.health_check()

            components_healthy = all([
                drive_health['status'] == 'healthy',
                image_health['status'] == 'healthy',
                excel_health['status'] == 'healthy',
                text_health['status'] == 'healthy',
                gemini_health['status'] == 'healthy'
            ])

            return {
                'status': 'healthy' if components_healthy else 'degraded',
                'is_monitoring': self.is_running,
                'processed_files_count': len(self.processing_history),
                'components': {
                    'google_drive': drive_health['status'],
                    'image_processor': image_health['status'],
                    'excel_processor': excel_health['status'],
                    'text_processor': text_health['status'],
                    'gemini_service': gemini_health['status']
                },
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Workflow health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }


# Global instance
document_ingestion_workflow = DocumentIngestionWorkflow()


async def get_document_ingestion_workflow() -> DocumentIngestionWorkflow:
    """Dependency for getting document ingestion workflow."""
    return document_ingestion_workflow