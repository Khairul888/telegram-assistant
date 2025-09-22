"""
Google Drive service for file monitoring, downloading, and management.
"""

import json
import asyncio
import aiohttp
import aiofiles
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
import tempfile
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

from ..core.config import settings
from ..core.logger import get_logger
from ..core.exceptions import TelegramAssistantException

logger = get_logger(__name__)


class GoogleDriveError(TelegramAssistantException):
    """Exception for Google Drive API errors."""
    pass


class GoogleDriveService:
    """Service for interacting with Google Drive API."""

    def __init__(self):
        self.folder_id = self._extract_folder_id(settings.google_drive_folder_id)
        self.credentials = None
        self.service = None
        self._temp_dir = None

    def _extract_folder_id(self, folder_input: str) -> str:
        """Extract folder ID from URL or return as-is if already an ID."""
        if "drive.google.com" in folder_input:
            # Extract from URL like: https://drive.google.com/drive/folders/1mkSfXU2li9KPTp0eENhSgmPbb-EinFJI
            parts = folder_input.split("/")
            for i, part in enumerate(parts):
                if part == "folders" and i + 1 < len(parts):
                    return parts[i + 1]
            raise GoogleDriveError(f"Could not extract folder ID from URL: {folder_input}")
        return folder_input

    async def _get_credentials(self) -> Credentials:
        """Get Google Drive API credentials."""
        if self.credentials and self.credentials.valid:
            return self.credentials

        try:
            # Try service account JSON path first
            if settings.google_service_account_json_path:
                self.credentials = Credentials.from_service_account_file(
                    settings.google_service_account_json_path,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
            # Try service account JSON content
            elif settings.google_service_account_json:
                service_account_info = json.loads(settings.google_service_account_json)
                self.credentials = Credentials.from_service_account_info(
                    service_account_info,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
            else:
                raise GoogleDriveError("No Google service account credentials configured")

            # Refresh if needed
            if not self.credentials.valid:
                if self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                else:
                    raise GoogleDriveError("Credentials are invalid and cannot be refreshed")

            logger.info("Google Drive credentials obtained successfully")
            return self.credentials

        except Exception as e:
            logger.error(f"Failed to get Google Drive credentials: {e}")
            raise GoogleDriveError(f"Authentication failed: {e}")

    async def _get_service(self):
        """Get Google Drive API service."""
        if self.service is None:
            credentials = await self._get_credentials()
            self.service = build('drive', 'v3', credentials=credentials)
        return self.service

    def _get_temp_dir(self) -> Path:
        """Get or create temporary directory for downloaded files."""
        if self._temp_dir is None:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="telegram_assistant_"))
            logger.info(f"Created temporary directory: {self._temp_dir}")
        return self._temp_dir

    async def list_files(
        self,
        file_types: Optional[List[str]] = None,
        modified_since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List files in the configured Google Drive folder.

        Args:
            file_types: Filter by file extensions (e.g., ['pdf', 'docx'])
            modified_since: Only return files modified after this date
            limit: Maximum number of files to return

        Returns:
            List of file metadata dictionaries
        """
        try:
            service = await self._get_service()

            # Build query
            query_parts = [f"'{self.folder_id}' in parents", "trashed=false"]

            if file_types:
                # Convert extensions to MIME type queries
                mime_queries = []
                for ext in file_types:
                    if ext.lower() in ['jpg', 'jpeg']:
                        mime_queries.append("mimeType='image/jpeg'")
                    elif ext.lower() == 'png':
                        mime_queries.append("mimeType='image/png'")
                    elif ext.lower() == 'pdf':
                        mime_queries.append("mimeType='application/pdf'")
                    elif ext.lower() == 'docx':
                        mime_queries.append("mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'")
                    elif ext.lower() == 'xlsx':
                        mime_queries.append("mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'")
                    elif ext.lower() == 'csv':
                        mime_queries.append("mimeType='text/csv'")

                if mime_queries:
                    query_parts.append(f"({' or '.join(mime_queries)})")

            if modified_since:
                formatted_date = modified_since.isoformat() + "Z"
                query_parts.append(f"modifiedTime > '{formatted_date}'")

            query = " and ".join(query_parts)

            logger.info(f"Querying Google Drive with: {query}")

            # Execute query
            result = service.files().list(
                q=query,
                pageSize=limit,
                fields="files(id,name,mimeType,size,modifiedTime,createdTime,parents,webViewLink)"
            ).execute()

            files = result.get('files', [])

            logger.info(f"Found {len(files)} files in Google Drive folder")

            # Convert to standardized format
            standardized_files = []
            for file in files:
                standardized_files.append({
                    'id': file['id'],
                    'name': file['name'],
                    'mime_type': file['mimeType'],
                    'size': int(file.get('size', 0)) if file.get('size') else 0,
                    'modified_time': file['modifiedTime'],
                    'created_time': file['createdTime'],
                    'web_view_link': file.get('webViewLink'),
                    'extension': Path(file['name']).suffix.lower().lstrip('.') if '.' in file['name'] else ''
                })

            return standardized_files

        except Exception as e:
            logger.error(f"Failed to list Google Drive files: {e}")
            raise GoogleDriveError(f"Failed to list files: {e}")

    async def download_file(self, file_id: str, file_name: str) -> Tuple[Path, Dict[str, Any]]:
        """
        Download a file from Google Drive.

        Args:
            file_id: Google Drive file ID
            file_name: Original file name

        Returns:
            Tuple of (local_file_path, file_metadata)
        """
        try:
            service = await self._get_service()
            temp_dir = self._get_temp_dir()

            # Get file metadata
            file_metadata = service.files().get(
                fileId=file_id,
                fields="id,name,mimeType,size,modifiedTime,createdTime,webViewLink"
            ).execute()

            # Create local file path
            safe_filename = "".join(c for c in file_name if c.isalnum() or c in "._- ")
            local_file_path = temp_dir / safe_filename

            logger.info(f"Downloading {file_name} (ID: {file_id}) to {local_file_path}")

            # Download file
            request = service.files().get_media(fileId=file_id)
            file_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_io, request)

            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    logger.debug(f"Download progress: {int(status.progress() * 100)}%")

            # Write to local file
            file_io.seek(0)
            async with aiofiles.open(local_file_path, 'wb') as f:
                await f.write(file_io.read())

            logger.info(f"Successfully downloaded {file_name} ({file_metadata.get('size', 0)} bytes)")

            return local_file_path, file_metadata

        except Exception as e:
            logger.error(f"Failed to download file {file_name}: {e}")
            raise GoogleDriveError(f"Download failed: {e}")

    async def get_new_files(self, since_minutes: int = 5) -> List[Dict[str, Any]]:
        """
        Get files that have been added or modified recently.

        Args:
            since_minutes: Look for files modified in the last N minutes

        Returns:
            List of new/modified files
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=since_minutes)

            # Get supported file types from config
            supported_extensions = settings.supported_file_types

            new_files = await self.list_files(
                file_types=supported_extensions,
                modified_since=cutoff_time,
                limit=50
            )

            logger.info(f"Found {len(new_files)} new/modified files in the last {since_minutes} minutes")

            return new_files

        except Exception as e:
            logger.error(f"Failed to get new files: {e}")
            raise GoogleDriveError(f"Failed to get new files: {e}")

    async def check_folder_access(self) -> Dict[str, Any]:
        """
        Check if the configured folder is accessible.

        Returns:
            Status dictionary with access information
        """
        try:
            service = await self._get_service()

            # Try to get folder metadata
            folder_metadata = service.files().get(
                fileId=self.folder_id,
                fields="id,name,mimeType,permissions"
            ).execute()

            # Try to list files (limited)
            result = service.files().list(
                q=f"'{self.folder_id}' in parents",
                pageSize=1,
                fields="files(id,name)"
            ).execute()

            files = result.get('files', [])

            return {
                'accessible': True,
                'folder_name': folder_metadata.get('name'),
                'folder_id': self.folder_id,
                'file_count': len(files),
                'message': 'Google Drive folder is accessible'
            }

        except Exception as e:
            logger.error(f"Google Drive folder access check failed: {e}")
            return {
                'accessible': False,
                'folder_id': self.folder_id,
                'error': str(e),
                'message': 'Google Drive folder is not accessible'
            }

    async def cleanup_temp_files(self, max_age_hours: int = 24):
        """
        Clean up temporary downloaded files older than max_age_hours.

        Args:
            max_age_hours: Delete files older than this many hours
        """
        try:
            if not self._temp_dir or not self._temp_dir.exists():
                return

            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            files_deleted = 0

            for file_path in self._temp_dir.iterdir():
                if file_path.is_file():
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        file_path.unlink()
                        files_deleted += 1

            logger.info(f"Cleaned up {files_deleted} temporary files older than {max_age_hours} hours")

        except Exception as e:
            logger.error(f"Failed to cleanup temporary files: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the Google Drive service.

        Returns:
            Health status dictionary
        """
        try:
            # Check credentials
            credentials = await self._get_credentials()

            # Check folder access
            folder_status = await self.check_folder_access()

            # Get recent files count
            recent_files = await self.get_new_files(since_minutes=60)

            return {
                'status': 'healthy' if folder_status['accessible'] else 'unhealthy',
                'credentials_valid': credentials.valid,
                'folder_accessible': folder_status['accessible'],
                'folder_name': folder_status.get('folder_name'),
                'recent_files_count': len(recent_files),
                'temp_dir': str(self._temp_dir) if self._temp_dir else None,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Google Drive health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def close(self):
        """Clean up resources."""
        try:
            await self.cleanup_temp_files(max_age_hours=1)  # Cleanup recent files
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Global instance
google_drive_service = GoogleDriveService()


async def get_google_drive_service() -> GoogleDriveService:
    """Dependency for getting Google Drive service."""
    return google_drive_service