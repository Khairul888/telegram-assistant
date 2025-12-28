"""Telegram API utilities for sending messages and handling callbacks."""
import os
import json
import urllib.request
import urllib.parse


class TelegramUtils:
    """Utilities for interacting with Telegram Bot API."""

    def __init__(self):
        """Initialize with bot token from environment."""
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN must be set in environment variables")

        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, chat_id: str, text: str):
        """
        Send text message to chat.

        Args:
            chat_id: Telegram chat ID
            text: Message text

        Returns:
            bool: True if successful
        """
        try:
            url = f"{self.base_url}/sendMessage"
            data = {"chat_id": chat_id, "text": text}

            data_encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_encoded, method='POST')

            with urllib.request.urlopen(req) as response:
                return response.status == 200
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    async def send_message_with_keyboard(self, chat_id: str, text: str, keyboard: dict):
        """
        Send message with inline keyboard.

        Args:
            chat_id: Telegram chat ID
            text: Message text
            keyboard: Inline keyboard markup dict

        Returns:
            bool: True if successful

        Example keyboard:
            {
                "inline_keyboard": [
                    [{"text": "Option 1", "callback_data": "option_1"}],
                    [{"text": "Option 2", "callback_data": "option_2"}]
                ]
            }
        """
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": text,
                "reply_markup": json.dumps(keyboard)
            }

            data_encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_encoded, method='POST')

            with urllib.request.urlopen(req) as response:
                return response.status == 200
        except Exception as e:
            print(f"Error sending message with keyboard: {e}")
            return False

    async def answer_callback_query(self, callback_query_id: str, text: str = ""):
        """
        Answer callback query to remove loading state.

        Args:
            callback_query_id: Callback query ID from update
            text: Optional notification text

        Returns:
            bool: True if successful
        """
        try:
            url = f"{self.base_url}/answerCallbackQuery"
            data = {"callback_query_id": callback_query_id}

            if text:
                data["text"] = text

            data_encoded = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=data_encoded, method='POST')

            with urllib.request.urlopen(req) as response:
                return response.status == 200
        except Exception as e:
            print(f"Error answering callback query: {e}")
            return False

    async def download_file(self, file_id: str) -> bytes:
        """
        Download file from Telegram servers.

        Args:
            file_id: Telegram file ID

        Returns:
            bytes: File content

        Raises:
            Exception: If download fails
        """
        try:
            # Get file path
            file_info_url = f"{self.base_url}/getFile?file_id={file_id}"
            req = urllib.request.Request(file_info_url)

            with urllib.request.urlopen(req) as response:
                file_info = json.loads(response.read().decode('utf-8'))

            if not file_info.get('ok'):
                raise Exception("Failed to get file info")

            file_path = file_info['result']['file_path']

            # Download file
            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            req = urllib.request.Request(download_url)

            with urllib.request.urlopen(req) as response:
                return response.read()

        except Exception as e:
            raise Exception(f"File download error: {str(e)}")

    def extract_file_info(self, message: dict) -> dict:
        """
        Extract file information from Telegram message.

        Args:
            message: Telegram message dict

        Returns:
            dict: {
                "has_file": bool,
                "file_type": str,  # "photo", "document", etc.
                "file_id": str,
                "file_name": str
            }
        """
        # Check for photo
        if "photo" in message:
            photos = message["photo"]
            largest_photo = max(photos, key=lambda p: p.get("file_size", 0))
            return {
                "has_file": True,
                "file_type": "photo",
                "file_id": largest_photo["file_id"],
                "file_name": f"photo_{largest_photo['file_id']}.jpg"
            }

        # Check for document
        if "document" in message:
            document = message["document"]
            return {
                "has_file": True,
                "file_type": "document",
                "file_id": document["file_id"],
                "file_name": document.get("file_name", "document")
            }

        return {
            "has_file": False,
            "file_type": None,
            "file_id": None,
            "file_name": None
        }
