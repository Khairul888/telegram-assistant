"""
Telegram Bot Service for handling bot interactions.
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import json

from ..core.config import settings
from ..core.logger import get_logger
from ..core.exceptions import TelegramAssistantException
from ..models import ChatMessage, ChatMessageCreate

logger = get_logger(__name__)


class TelegramAPIError(TelegramAssistantException):
    """Exception for Telegram API errors."""
    pass


class TelegramService:
    """Service for interacting with Telegram Bot API."""

    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make API request to Telegram."""
        url = f"{self.base_url}/{endpoint}"
        session = await self._get_session()

        try:
            if files:
                # For file uploads, use FormData
                form_data = aiohttp.FormData()
                if data:
                    for key, value in data.items():
                        if isinstance(value, (dict, list)):
                            form_data.add_field(key, json.dumps(value))
                        else:
                            form_data.add_field(key, str(value))

                for key, file_data in files.items():
                    form_data.add_field(key, file_data)

                async with session.request(method, url, data=form_data) as response:
                    result = await response.json()
            else:
                # For regular API calls
                async with session.request(method, url, json=data) as response:
                    result = await response.json()

            if not result.get("ok", False):
                error_msg = result.get("description", "Unknown Telegram API error")
                logger.error(f"Telegram API error: {error_msg}", extra={
                    "endpoint": endpoint,
                    "error_code": result.get("error_code"),
                    "data": data
                })
                raise TelegramAPIError(f"Telegram API error: {error_msg}")

            return result

        except aiohttp.ClientError as e:
            logger.error(f"HTTP error calling Telegram API: {e}", extra={
                "endpoint": endpoint,
                "method": method
            })
            raise TelegramAPIError(f"HTTP error: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Telegram API: {e}")
            raise TelegramAPIError(f"Invalid JSON response: {e}")

    async def get_me(self) -> Dict[str, Any]:
        """Get bot information."""
        logger.debug("Getting bot information")
        return await self._make_request("GET", "getMe")

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "Markdown",
        reply_markup: Optional[Dict] = None,
        disable_web_page_preview: bool = True
    ) -> Dict[str, Any]:
        """Send a text message."""
        target_chat_id = chat_id or self.chat_id

        data = {
            "chat_id": target_chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }

        if reply_markup:
            data["reply_markup"] = reply_markup

        logger.info(f"Sending message to chat {target_chat_id}", extra={
            "chat_id": target_chat_id,
            "text_length": len(text)
        })

        return await self._make_request("POST", "sendMessage", data)

    async def send_document(
        self,
        document: Union[str, bytes],
        filename: Optional[str] = None,
        caption: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a document."""
        target_chat_id = chat_id or self.chat_id

        data = {"chat_id": target_chat_id}
        if caption:
            data["caption"] = caption

        files = {}
        if isinstance(document, str):
            # File path or URL
            data["document"] = document
        else:
            # Binary data
            files["document"] = document

        logger.info(f"Sending document to chat {target_chat_id}", extra={
            "chat_id": target_chat_id,
            "filename": filename,
            "caption_length": len(caption) if caption else 0
        })

        return await self._make_request("POST", "sendDocument", data, files)

    async def send_photo(
        self,
        photo: Union[str, bytes],
        caption: Optional[str] = None,
        chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a photo."""
        target_chat_id = chat_id or self.chat_id

        data = {"chat_id": target_chat_id}
        if caption:
            data["caption"] = caption

        files = {}
        if isinstance(photo, str):
            data["photo"] = photo
        else:
            files["photo"] = photo

        logger.info(f"Sending photo to chat {target_chat_id}", extra={
            "chat_id": target_chat_id,
            "caption_length": len(caption) if caption else 0
        })

        return await self._make_request("POST", "sendPhoto", data, files)

    async def edit_message_text(
        self,
        message_id: int,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "Markdown",
        reply_markup: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Edit a message text."""
        target_chat_id = chat_id or self.chat_id

        data = {
            "chat_id": target_chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": parse_mode
        }

        if reply_markup:
            data["reply_markup"] = reply_markup

        logger.info(f"Editing message {message_id} in chat {target_chat_id}")

        return await self._make_request("POST", "editMessageText", data)

    async def delete_message(
        self,
        message_id: int,
        chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a message."""
        target_chat_id = chat_id or self.chat_id

        data = {
            "chat_id": target_chat_id,
            "message_id": message_id
        }

        logger.info(f"Deleting message {message_id} in chat {target_chat_id}")

        return await self._make_request("POST", "deleteMessage", data)

    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """Get file information."""
        data = {"file_id": file_id}
        return await self._make_request("POST", "getFile", data)

    async def download_file(self, file_path: str) -> bytes:
        """Download a file from Telegram servers."""
        download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
        session = await self._get_session()

        try:
            async with session.get(download_url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    raise TelegramAPIError(f"Failed to download file: HTTP {response.status}")
        except aiohttp.ClientError as e:
            logger.error(f"Error downloading file: {e}")
            raise TelegramAPIError(f"Download error: {e}")

    async def set_webhook(self, webhook_url: str) -> Dict[str, Any]:
        """Set webhook URL for receiving updates."""
        data = {
            "url": webhook_url,
            "allowed_updates": ["message", "callback_query", "inline_query"]
        }

        logger.info(f"Setting webhook to: {webhook_url}")
        return await self._make_request("POST", "setWebhook", data)

    async def delete_webhook(self) -> Dict[str, Any]:
        """Delete webhook (switch to polling mode)."""
        logger.info("Deleting webhook")
        return await self._make_request("POST", "deleteWebhook")

    async def get_webhook_info(self) -> Dict[str, Any]:
        """Get current webhook status."""
        return await self._make_request("GET", "getWebhookInfo")

    async def get_updates(
        self,
        offset: Optional[int] = None,
        limit: int = 100,
        timeout: int = 0
    ) -> Dict[str, Any]:
        """Get updates using long polling (for development/testing)."""
        data = {
            "limit": limit,
            "timeout": timeout
        }
        if offset:
            data["offset"] = offset

        return await self._make_request("GET", "getUpdates", data)

    def parse_update(self, update: Dict[str, Any]) -> Optional[ChatMessageCreate]:
        """Parse Telegram update into ChatMessage model."""
        try:
            if "message" in update:
                message = update["message"]

                # Extract message info
                message_id = str(message["message_id"])
                chat_id = str(message["chat"]["id"])
                date = datetime.fromtimestamp(message["date"])

                # Extract user info
                user = message.get("from", {})
                user_id = str(user.get("id", ""))
                username = user.get("username")
                first_name = user.get("first_name")
                last_name = user.get("last_name")

                # Extract message content
                content = ""
                message_type = "user"

                if "text" in message:
                    content = message["text"]
                elif "caption" in message:
                    content = message["caption"]
                elif "document" in message:
                    content = f"[Document: {message['document'].get('file_name', 'Unknown')}]"
                elif "photo" in message:
                    content = "[Photo]"
                elif "voice" in message:
                    content = "[Voice message]"
                else:
                    content = "[Unsupported message type]"

                return ChatMessageCreate(
                    message_id=message_id,
                    chat_id=chat_id,
                    message_type=message_type,
                    content=content,
                    user_id=user_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    telegram_date=date
                )

        except Exception as e:
            logger.error(f"Error parsing Telegram update: {e}", extra={
                "update": update
            })
            return None

    def create_keyboard(self, buttons: List[List[Dict[str, str]]]) -> Dict[str, Any]:
        """Create inline keyboard markup."""
        return {
            "inline_keyboard": buttons
        }

    def create_reply_keyboard(
        self,
        buttons: List[List[str]],
        resize_keyboard: bool = True,
        one_time_keyboard: bool = False
    ) -> Dict[str, Any]:
        """Create reply keyboard markup."""
        keyboard = []
        for row in buttons:
            keyboard_row = []
            for button_text in row:
                keyboard_row.append({"text": button_text})
            keyboard.append(keyboard_row)

        return {
            "keyboard": keyboard,
            "resize_keyboard": resize_keyboard,
            "one_time_keyboard": one_time_keyboard
        }

    async def health_check(self) -> Dict[str, Any]:
        """Check if Telegram bot is accessible."""
        try:
            bot_info = await self.get_me()
            return {
                "status": "healthy",
                "bot_info": bot_info.get("result", {}),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Telegram health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


# Global instance
telegram_service = TelegramService()


async def get_telegram_service() -> TelegramService:
    """Dependency for getting Telegram service."""
    return telegram_service