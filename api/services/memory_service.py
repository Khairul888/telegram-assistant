"""Conversation memory service for trip-scoped chat history."""
from collections import deque
from typing import Dict, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage


class ConversationMemoryService:
    """
    Manages conversation memory per trip.

    Design:
    - In-memory storage (no database persistence)
    - Per-trip scope: All users in same trip share conversation history
    - Auto-trimming: Keeps last 15 messages per trip (rolling window)
    - Thread-safe: Dict operations are atomic in Python (GIL)
    """

    def __init__(self, max_messages: int = 15):
        """
        Initialize memory service.

        Args:
            max_messages: Maximum messages to retain per trip (default 15)
        """
        # Storage: {trip_id: deque([HumanMessage(), AIMessage(), ...])}
        self._memory: Dict[int, deque] = {}
        self.max_messages = max_messages

    def add_message(self, trip_id: int, message: BaseMessage) -> None:
        """
        Add a message to trip's conversation history.

        Args:
            trip_id: Trip ID
            message: LangChain message object (HumanMessage or AIMessage)
        """
        if trip_id not in self._memory:
            self._memory[trip_id] = deque(maxlen=self.max_messages)

        self._memory[trip_id].append(message)

    def add_user_message(self, trip_id: int, content: str) -> None:
        """
        Add user message to history.

        Args:
            trip_id: Trip ID
            content: User message text
        """
        self.add_message(trip_id, HumanMessage(content=content))

    def add_ai_message(self, trip_id: int, content: str) -> None:
        """
        Add AI response to history.

        Args:
            trip_id: Trip ID
            content: AI response text
        """
        self.add_message(trip_id, AIMessage(content=content))

    def get_history(self, trip_id: int, limit: Optional[int] = None) -> List[BaseMessage]:
        """
        Get conversation history for trip.

        Args:
            trip_id: Trip ID
            limit: Optional limit on number of messages (default: all)

        Returns:
            List of LangChain message objects in chronological order
        """
        if trip_id not in self._memory:
            return []

        messages = list(self._memory[trip_id])

        if limit is not None and limit > 0:
            return messages[-limit:]

        return messages

    def get_history_as_text(self, trip_id: int, limit: Optional[int] = None) -> str:
        """
        Get formatted conversation history as text.

        Args:
            trip_id: Trip ID
            limit: Optional limit on number of messages

        Returns:
            Formatted conversation history string
        """
        messages = self.get_history(trip_id, limit)

        if not messages:
            return "No previous conversation."

        lines = []
        for msg in messages:
            role = "User" if isinstance(msg, HumanMessage) else "Assistant"
            lines.append(f"{role}: {msg.content}")

        return "\n".join(lines)

    def clear_history(self, trip_id: int) -> None:
        """
        Clear conversation history for trip.

        Args:
            trip_id: Trip ID
        """
        if trip_id in self._memory:
            del self._memory[trip_id]

    def get_stats(self) -> Dict:
        """
        Get memory statistics for debugging.

        Returns:
            Dict with memory stats
        """
        return {
            "total_trips": len(self._memory),
            "trips": {
                trip_id: len(messages)
                for trip_id, messages in self._memory.items()
            }
        }
