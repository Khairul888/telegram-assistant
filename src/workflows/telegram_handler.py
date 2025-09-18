"""
Telegram message processing and routing workflow.
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from ..core.logger import get_logger
from ..core.database import get_database_session
from ..services.telegram_service import get_telegram_service, TelegramAPIError
from ..models import ChatMessage, ChatMessageCreate, UserProfile, UserProfileCreate
from ..workflows.document_processor import DocumentProcessor
from ..ai.gemini_service import GeminiService
from ..core.exceptions import TelegramAssistantException

logger = get_logger(__name__)


class TelegramMessageHandler:
    """Handles incoming Telegram messages and coordinates responses."""

    def __init__(self):
        self.document_processor = DocumentProcessor()
        self.ai_service = GeminiService()
        self.conversation_memory: Dict[str, List[Dict]] = {}

    async def handle_update(self, update: Dict[str, Any]) -> None:
        """Main entry point for handling Telegram updates."""
        try:
            # Parse the update
            telegram_service = await get_telegram_service()
            message_data = telegram_service.parse_update(update)

            if not message_data:
                logger.warning("Unable to parse Telegram update", extra={"update": update})
                return

            # Store message in database
            async with get_database_session() as db_session:
                await self._store_message(db_session, message_data)
                await self._ensure_user_profile(db_session, message_data)

            # Route message based on type
            if "message" in update:
                await self._handle_message(update["message"], message_data)
            elif "callback_query" in update:
                await self._handle_callback_query(update["callback_query"])
            else:
                logger.info("Unhandled update type", extra={"update_keys": list(update.keys())})

        except Exception as e:
            logger.error(f"Error handling Telegram update: {e}", extra={
                "update": update,
                "error_type": type(e).__name__
            })

    async def _handle_message(self, message: Dict[str, Any], message_data: ChatMessageCreate) -> None:
        """Handle regular text messages and media."""
        try:
            chat_id = message_data.chat_id
            content = message_data.content

            # Handle commands
            if content.startswith('/'):
                await self._handle_command(message, message_data)
                return

            # Handle file uploads
            if self._has_file(message):
                await self._handle_file_message(message, message_data)
                return

            # Handle regular text messages
            await self._handle_text_message(message, message_data)

        except Exception as e:
            logger.error(f"Error handling message: {e}", extra={
                "message": message,
                "error_type": type(e).__name__
            })
            await self._send_error_message(message_data.chat_id, "Sorry, I encountered an error processing your message.")

    async def _handle_command(self, message: Dict[str, Any], message_data: ChatMessageCreate) -> None:
        """Handle bot commands."""
        content = message_data.content.lower()
        chat_id = message_data.chat_id

        try:
            if content.startswith('/start'):
                await self._handle_start_command(chat_id, message_data)
            elif content.startswith('/help'):
                await self._handle_help_command(chat_id)
            elif content.startswith('/status'):
                await self._handle_status_command(chat_id)
            elif content.startswith('/clear'):
                await self._handle_clear_command(chat_id)
            elif content.startswith('/search'):
                await self._handle_search_command(chat_id, content)
            else:
                await self._handle_unknown_command(chat_id, content)

        except Exception as e:
            logger.error(f"Error handling command: {e}", extra={
                "command": content,
                "chat_id": chat_id
            })
            await self._send_error_message(chat_id, "Sorry, I couldn't process that command.")

    async def _handle_text_message(self, message: Dict[str, Any], message_data: ChatMessageCreate) -> None:
        """Handle regular text messages with AI processing."""
        chat_id = message_data.chat_id
        user_text = message_data.content

        try:
            # Send typing indicator
            telegram_service = await get_telegram_service()

            # Get conversation context
            context = await self._get_conversation_context(chat_id)

            # Get relevant documents from vector search
            relevant_docs = await self._search_relevant_documents(user_text)

            # Generate AI response
            ai_response = await self._generate_ai_response(
                user_text=user_text,
                context=context,
                relevant_docs=relevant_docs,
                user_info=message_data
            )

            # Send response
            await telegram_service.send_message(ai_response, chat_id)

            # Store bot response
            bot_message = ChatMessageCreate(
                message_id=f"bot_{datetime.now().timestamp()}",
                chat_id=chat_id,
                message_type="bot",
                content=ai_response
            )

            async with get_database_session() as db_session:
                await self._store_message(db_session, bot_message)

            # Update conversation memory
            self._update_conversation_memory(chat_id, user_text, ai_response)

        except Exception as e:
            logger.error(f"Error processing text message: {e}", extra={
                "user_text": user_text,
                "chat_id": chat_id
            })
            await self._send_error_message(chat_id, "I'm having trouble processing your message right now. Please try again.")

    async def _handle_file_message(self, message: Dict[str, Any], message_data: ChatMessageCreate) -> None:
        """Handle file uploads (documents, images, etc.)."""
        chat_id = message_data.chat_id

        try:
            telegram_service = await get_telegram_service()

            # Send initial response
            await telegram_service.send_message(
                "📄 I received your file! Processing it now...",
                chat_id
            )

            # Extract file information
            file_info = await self._extract_file_info(message)

            if not file_info:
                await telegram_service.send_message(
                    "❌ Sorry, I couldn't process this file type.",
                    chat_id
                )
                return

            # Download file
            file_data = await telegram_service.download_file(file_info["file_path"])

            # Process file
            processing_result = await self.document_processor.process_file(
                file_data=file_data,
                filename=file_info["filename"],
                file_type=file_info["file_type"],
                source="telegram"
            )

            # Send processing result
            if processing_result["success"]:
                response = f"✅ **File processed successfully!**\n\n"
                response += f"📋 **Summary:** {processing_result['summary']}\n\n"
                response += f"🔑 **Key Topics:** {', '.join(processing_result['keywords'])}\n\n"
                response += f"💾 The document has been indexed and is now searchable."
            else:
                response = f"❌ **Processing failed:** {processing_result['error']}"

            await telegram_service.send_message(response, chat_id)

        except Exception as e:
            logger.error(f"Error handling file message: {e}", extra={
                "message": message,
                "chat_id": chat_id
            })
            await self._send_error_message(chat_id, "Sorry, I couldn't process your file.")

    async def _handle_start_command(self, chat_id: str, message_data: ChatMessageCreate) -> None:
        """Handle /start command."""
        welcome_message = f"""
🤖 **Welcome to your AI Document Assistant!**

Hello {message_data.first_name or 'there'}! I'm here to help you analyze and search through your documents.

**What I can do:**
📄 Process PDFs, Word docs, images, and spreadsheets
🔍 Search through your uploaded documents
💬 Answer questions about your files
📊 Extract insights and summaries

**Getting Started:**
1. Upload any document or image
2. Ask me questions about your files
3. Use /search <query> to find specific information

**Commands:**
/help - Show this help message
/status - Check system status
/search <query> - Search your documents
/clear - Clear conversation history

Ready to get started? Just upload a file or ask me anything!
"""

        telegram_service = await get_telegram_service()
        await telegram_service.send_message(welcome_message, chat_id)

    async def _handle_help_command(self, chat_id: str) -> None:
        """Handle /help command."""
        help_message = """
🔧 **Available Commands:**

🏠 `/start` - Welcome message and introduction
❓ `/help` - Show this help message
📊 `/status` - Check system health and statistics
🔍 `/search <query>` - Search through your documents
🗑️ `/clear` - Clear conversation history

📁 **Supported File Types:**
• PDFs, Word documents (.docx)
• Images (JPG, PNG, GIF, WEBP)
• Spreadsheets (Excel, CSV)
• Text files (.txt)

💡 **Tips:**
• Upload multiple files to build your knowledge base
• Ask specific questions about your documents
• Use natural language - I understand context!
• Mention specific documents by name for targeted searches

Need more help? Just ask me anything!
"""

        telegram_service = await get_telegram_service()
        await telegram_service.send_message(help_message, chat_id)

    async def _handle_status_command(self, chat_id: str) -> None:
        """Handle /status command."""
        try:
            # Get system status
            async with get_database_session() as db_session:
                # Get document count
                from sqlalchemy import select, func
                from ..models import Document
                doc_result = await db_session.execute(select(func.count()).select_from(Document))
                doc_count = doc_result.scalar() or 0

                # Get recent messages count
                from ..models import ChatMessage
                recent_time = datetime.now() - timedelta(days=7)
                msg_result = await db_session.execute(
                    select(func.count()).select_from(ChatMessage).where(
                        ChatMessage.created_at >= recent_time
                    )
                )
                recent_msg_count = msg_result.scalar() or 0

            # Check AI service
            ai_status = await self.ai_service.health_check()

            status_message = f"""
📊 **System Status**

🗄️ **Documents:** {doc_count} files indexed
💬 **Recent Activity:** {recent_msg_count} messages (7 days)
🤖 **AI Service:** {'✅ Online' if ai_status['status'] == 'healthy' else '❌ Offline'}
📡 **Database:** ✅ Connected

🕐 **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

All systems operational! 🚀
"""

            telegram_service = await get_telegram_service()
            await telegram_service.send_message(status_message, chat_id)

        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await self._send_error_message(chat_id, "Unable to retrieve system status.")

    async def _handle_clear_command(self, chat_id: str) -> None:
        """Handle /clear command."""
        # Clear conversation memory
        if chat_id in self.conversation_memory:
            del self.conversation_memory[chat_id]

        telegram_service = await get_telegram_service()
        await telegram_service.send_message(
            "🗑️ Conversation history cleared! Starting fresh.",
            chat_id
        )

    async def _handle_search_command(self, chat_id: str, content: str) -> None:
        """Handle /search command."""
        # Extract search query
        query = content.replace('/search', '').strip()

        if not query:
            telegram_service = await get_telegram_service()
            await telegram_service.send_message(
                "Please provide a search query. Example: `/search machine learning algorithms`",
                chat_id
            )
            return

        # Perform search
        search_results = await self._search_relevant_documents(query, limit=5)

        if not search_results:
            telegram_service = await get_telegram_service()
            await telegram_service.send_message(
                f"🔍 No results found for: *{query}*\n\nTry uploading some documents first!",
                chat_id
            )
            return

        # Format results
        response = f"🔍 **Search Results for:** *{query}*\n\n"
        for i, result in enumerate(search_results, 1):
            response += f"**{i}.** {result['filename']}\n"
            response += f"📄 {result['snippet'][:200]}...\n"
            response += f"🎯 Match: {result['score']:.0%}\n\n"

        telegram_service = await get_telegram_service()
        await telegram_service.send_message(response, chat_id)

    async def _handle_unknown_command(self, chat_id: str, command: str) -> None:
        """Handle unknown commands."""
        response = f"❓ Unknown command: `{command}`\n\nUse /help to see available commands."

        telegram_service = await get_telegram_service()
        await telegram_service.send_message(response, chat_id)

    async def _handle_callback_query(self, callback_query: Dict[str, Any]) -> None:
        """Handle inline keyboard callbacks."""
        # Implementation for interactive buttons
        pass

    def _has_file(self, message: Dict[str, Any]) -> bool:
        """Check if message contains a file."""
        return any(key in message for key in ["document", "photo", "voice", "video", "audio"])

    async def _extract_file_info(self, message: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Extract file information from message."""
        telegram_service = await get_telegram_service()

        try:
            if "document" in message:
                doc = message["document"]
                file_info = await telegram_service.get_file(doc["file_id"])
                return {
                    "file_id": doc["file_id"],
                    "filename": doc.get("file_name", "document"),
                    "file_type": doc.get("mime_type", "application/octet-stream"),
                    "file_path": file_info["result"]["file_path"],
                    "file_size": doc.get("file_size", 0)
                }
            elif "photo" in message:
                # Get largest photo
                photo = max(message["photo"], key=lambda p: p.get("file_size", 0))
                file_info = await telegram_service.get_file(photo["file_id"])
                return {
                    "file_id": photo["file_id"],
                    "filename": "image.jpg",
                    "file_type": "image/jpeg",
                    "file_path": file_info["result"]["file_path"],
                    "file_size": photo.get("file_size", 0)
                }

        except Exception as e:
            logger.error(f"Error extracting file info: {e}")

        return None

    async def _get_conversation_context(self, chat_id: str, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation context."""
        # Return from memory first
        if chat_id in self.conversation_memory:
            return self.conversation_memory[chat_id][-limit:]

        # Fallback to database
        try:
            async with get_database_session() as db_session:
                from sqlalchemy import select
                from ..models import ChatMessage

                result = await db_session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.chat_id == chat_id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(limit)
                )
                messages = result.scalars().all()

                context = []
                for msg in reversed(messages):
                    context.append({
                        "role": "user" if msg.message_type == "user" else "assistant",
                        "content": msg.content
                    })

                return context

        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return []

    async def _search_relevant_documents(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search for relevant documents using vector similarity."""
        # TODO: Implement vector search with Pinecone
        # For now, return empty list
        return []

    async def _generate_ai_response(
        self,
        user_text: str,
        context: List[Dict[str, str]],
        relevant_docs: List[Dict[str, Any]],
        user_info: ChatMessageCreate
    ) -> str:
        """Generate AI response using Gemini."""
        try:
            # Build context for AI
            system_prompt = """You are an intelligent document assistant. You help users analyze, search, and understand their uploaded documents. Be helpful, concise, and accurate."""

            # Build conversation context
            conversation_context = ""
            if context:
                conversation_context = "\n\n**Recent Conversation:**\n"
                for msg in context[-5:]:  # Last 5 messages
                    role = "User" if msg["role"] == "user" else "Assistant"
                    conversation_context += f"{role}: {msg['content']}\n"

            # Build document context
            document_context = ""
            if relevant_docs:
                document_context = "\n\n**Relevant Documents:**\n"
                for doc in relevant_docs:
                    document_context += f"- {doc['filename']}: {doc['snippet']}\n"

            # Combine all context
            full_prompt = f"{system_prompt}{conversation_context}{document_context}\n\nUser Question: {user_text}"

            # Generate response
            response = await self.ai_service.generate_response(full_prompt)
            return response

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "I'm having trouble processing your request right now. Please try again in a moment."

    def _update_conversation_memory(self, chat_id: str, user_text: str, ai_response: str) -> None:
        """Update in-memory conversation context."""
        if chat_id not in self.conversation_memory:
            self.conversation_memory[chat_id] = []

        # Add user message
        self.conversation_memory[chat_id].append({
            "role": "user",
            "content": user_text
        })

        # Add AI response
        self.conversation_memory[chat_id].append({
            "role": "assistant",
            "content": ai_response
        })

        # Keep only recent messages (memory window)
        from ..core.config import settings
        max_memory = getattr(settings, 'memory_window_size', 40)
        if len(self.conversation_memory[chat_id]) > max_memory:
            self.conversation_memory[chat_id] = self.conversation_memory[chat_id][-max_memory:]

    async def _store_message(self, db_session, message_data: ChatMessageCreate) -> None:
        """Store message in database."""
        try:
            from ..models import ChatMessage
            message = ChatMessage(**message_data.model_dump())
            db_session.add(message)
            await db_session.commit()
        except Exception as e:
            logger.error(f"Error storing message: {e}")
            await db_session.rollback()

    async def _ensure_user_profile(self, db_session, message_data: ChatMessageCreate) -> None:
        """Ensure user profile exists."""
        try:
            from sqlalchemy import select
            from ..models import UserProfile

            # Check if user exists
            result = await db_session.execute(
                select(UserProfile).where(UserProfile.telegram_user_id == message_data.user_id)
            )
            existing_user = result.scalar_one_or_none()

            if not existing_user:
                # Create new user profile
                user_profile = UserProfile(
                    telegram_user_id=message_data.user_id,
                    telegram_chat_id=message_data.chat_id,
                    username=message_data.username,
                    first_name=message_data.first_name,
                    last_name=message_data.last_name
                )
                db_session.add(user_profile)
                await db_session.commit()

                logger.info(f"Created new user profile", extra={
                    "user_id": message_data.user_id,
                    "username": message_data.username
                })

        except Exception as e:
            logger.error(f"Error ensuring user profile: {e}")
            await db_session.rollback()

    async def _send_error_message(self, chat_id: str, error_text: str) -> None:
        """Send error message to user."""
        try:
            telegram_service = await get_telegram_service()
            await telegram_service.send_message(f"❌ {error_text}", chat_id)
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")


# Global instance
telegram_message_handler = TelegramMessageHandler()