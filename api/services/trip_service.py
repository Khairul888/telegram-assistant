"""Trip management service for trip-based memory system."""
from typing import Optional, List, Dict
from datetime import datetime


class TripService:
    """Manages trip creation, retrieval, and activity tracking."""

    def __init__(self, supabase_client):
        """Initialize with Supabase client."""
        self.supabase = supabase_client

    async def create_trip(self, user_id: str, chat_id: str, chat_type: str,
                         trip_name: str, location: str, participants: List[str]) -> Dict:
        """
        Create a new trip and set as current trip for user in this chat.

        Args:
            user_id: Telegram user ID (creator)
            chat_id: Telegram chat ID (group ID for groups, user ID for DMs)
            chat_type: Chat type ('private', 'group', or 'supergroup')
            trip_name: Name of the trip (e.g., "Tokyo 2025")
            location: Trip destination (e.g., "Tokyo, Japan")
            participants: List of participant names (e.g., ["Alice", "Bob"])

        Returns:
            dict: {"success": bool, "trip_id": int, "trip": dict} or {"success": False, "error": str}
        """
        try:
            trip_data = {
                "user_id": user_id,           # Creator (audit trail)
                "chat_id": chat_id,           # Ownership scope (group or DM)
                "chat_type": chat_type,       # Chat type
                "trip_name": trip_name,
                "location": location,
                "participants": participants,  # JSONB array
                "status": "active",
                "last_activity_at": datetime.now().isoformat()
            }

            # Insert trip
            result = self.supabase.table('trips').insert(trip_data).execute()

            if not result.data:
                return {"success": False, "error": "Failed to create trip"}

            trip_id = result.data[0]['id']

            # Set as current trip in user session for this chat
            await self._set_current_trip(user_id, chat_id, trip_id)

            return {
                "success": True,
                "trip_id": trip_id,
                "trip": result.data[0]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_current_trip(self, user_id: str, chat_id: str) -> Optional[Dict]:
        """
        Get current active trip for this chat.

        Behavior differs by chat type:
        - Group chats: Always use latest active trip (shared across all users)
        - DMs: Allow per-user trip selection (user can switch between trips)

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID (group ID or user ID for DMs)

        Returns:
            dict: Trip data or None if no trips exist
        """
        try:
            # Determine chat type: DMs have chat_id == user_id
            is_dm = (chat_id == user_id)

            # For DMs only: Check user's session for current_trip_id
            if is_dm:
                session_result = self.supabase.table('user_sessions')\
                    .select('current_trip_id')\
                    .eq('user_id', user_id)\
                    .eq('chat_id', chat_id)\
                    .execute()

                # If session exists and has current_trip_id
                if session_result.data and len(session_result.data) > 0:
                    current_trip_id = session_result.data[0].get('current_trip_id')

                    if current_trip_id:
                        # Get the trip and verify it belongs to this chat
                        trip_result = self.supabase.table('trips')\
                            .select('*')\
                            .eq('id', current_trip_id)\
                            .eq('chat_id', chat_id)\
                            .execute()

                        if trip_result.data and len(trip_result.data) > 0:
                            return trip_result.data[0]

            # For groups: Always use latest active trip (no per-user selection)
            # For DMs: Fallback if no session found
            result = self.supabase.table('trips')\
                .select('*')\
                .eq('chat_id', chat_id)\
                .eq('status', 'active')\
                .order('last_activity_at', desc=True)\
                .limit(1)\
                .execute()

            if result.data and len(result.data) > 0:
                trip = result.data[0]
                # Only set session for DMs (not groups - groups share trip context)
                if is_dm:
                    await self._set_current_trip(user_id, chat_id, trip['id'])
                return trip

            return None
        except Exception as e:
            print(f"Error getting current trip: {e}")
            return None

    async def list_trips(self, user_id: str, chat_id: str) -> List[Dict]:
        """
        List all trips for this chat, ordered by most recent activity.

        Args:
            user_id: Telegram user ID (for future per-user permissions)
            chat_id: Telegram chat ID (group ID or user ID for DMs)

        Returns:
            list: List of trip dictionaries
        """
        try:
            result = self.supabase.table('trips')\
                .select('*')\
                .eq('chat_id', chat_id)\
                .order('last_activity_at', desc=True)\
                .execute()

            return result.data if result.data else []
        except Exception as e:
            print(f"Error listing trips: {e}")
            return []

    async def get_trip_by_id(self, trip_id: int) -> Optional[Dict]:
        """
        Get trip by ID.

        Args:
            trip_id: Trip ID

        Returns:
            dict: Trip data or None if not found
        """
        try:
            result = self.supabase.table('trips')\
                .select('*')\
                .eq('id', trip_id)\
                .execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error getting trip by ID: {e}")
            return None

    async def update_trip_activity(self, trip_id: int):
        """
        Update last_activity_at timestamp for trip.
        Called whenever trip-related action occurs.

        Args:
            trip_id: Trip ID to update
        """
        try:
            self.supabase.table('trips')\
                .update({"last_activity_at": datetime.now().isoformat()})\
                .eq('id', trip_id)\
                .execute()
        except Exception as e:
            print(f"Error updating trip activity: {e}")

    async def _set_current_trip(self, user_id: str, chat_id: str, trip_id: int):
        """
        Set current trip in user session for this chat.
        Uses upsert to create or update session.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID (group ID or user ID for DMs)
            trip_id: Trip ID to set as current
        """
        try:
            session_data = {
                "user_id": user_id,
                "chat_id": chat_id,
                "current_trip_id": trip_id,
                "last_activity_at": datetime.now().isoformat()
            }

            # Upsert user session with composite key (user_id, chat_id)
            self.supabase.table('user_sessions')\
                .upsert(session_data, on_conflict='user_id,chat_id')\
                .execute()
        except Exception as e:
            print(f"Error setting current trip: {e}")

    async def get_or_update_session(self, user_id: str, chat_id: str,
                                   state: str = None, context: Dict = None) -> Dict:
        """
        Get or create user session for this chat with optional state/context update.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID (group ID or user ID for DMs)
            state: Optional conversation state to set
            context: Optional context data to store

        Returns:
            dict: Session data
        """
        try:
            # Try to get existing session for this user in this chat
            result = self.supabase.table('user_sessions')\
                .select('*')\
                .eq('user_id', user_id)\
                .eq('chat_id', chat_id)\
                .execute()

            if result.data and len(result.data) > 0:
                session = result.data[0]

                # Update if state or context provided
                if state is not None or context is not None:
                    updates = {"last_activity_at": datetime.now().isoformat()}
                    if state is not None:
                        updates["conversation_state"] = state
                    if context is not None:
                        updates["conversation_context"] = context

                    self.supabase.table('user_sessions')\
                        .update(updates)\
                        .eq('user_id', user_id)\
                        .eq('chat_id', chat_id)\
                        .execute()

                    # Merge updates into session
                    session.update(updates)

                return session
            else:
                # Create new session for this user in this chat
                session_data = {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "conversation_state": state,
                    "conversation_context": context or {},
                    "last_activity_at": datetime.now().isoformat()
                }

                result = self.supabase.table('user_sessions')\
                    .insert(session_data)\
                    .execute()

                return result.data[0] if result.data else {}
        except Exception as e:
            print(f"Error managing session: {e}")
            return {}

    async def clear_conversation_state(self, user_id: str, chat_id: str):
        """
        Clear conversation state after completing multi-step flow.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID (group ID or user ID for DMs)
        """
        try:
            self.supabase.table('user_sessions')\
                .update({
                    "conversation_state": None,
                    "conversation_context": None
                })\
                .eq('user_id', user_id)\
                .eq('chat_id', chat_id)\
                .execute()
        except Exception as e:
            print(f"Error clearing conversation state: {e}")

    async def switch_trip(self, user_id: str, chat_id: str, trip_id: int) -> Dict:
        """
        Switch active trip for this chat.
        Verifies trip belongs to this chat before switching.

        Args:
            user_id: Telegram user ID requesting the switch
            chat_id: Telegram chat ID (group ID or user ID for DMs)
            trip_id: Trip ID to switch to

        Returns:
            dict: {"success": bool, "trip": dict} or {"success": False, "error": str}
        """
        try:
            # Verify trip exists and belongs to this chat
            trip_result = self.supabase.table('trips')\
                .select('*')\
                .eq('id', trip_id)\
                .eq('chat_id', chat_id)\
                .execute()

            if not trip_result.data or len(trip_result.data) == 0:
                return {"success": False, "error": "Trip not found in this chat"}

            trip = trip_result.data[0]

            # Set as current trip for this user in this chat
            await self._set_current_trip(user_id, chat_id, trip_id)

            # Update trip activity timestamp
            await self.update_trip_activity(trip_id)

            return {"success": True, "trip": trip}
        except Exception as e:
            print(f"Error switching trip: {e}")
            return {"success": False, "error": str(e)}
