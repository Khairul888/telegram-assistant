"""TripAgent for trip metadata and management."""
from api.agents.base_agent import BaseAgent
from api.agents.tools.trip_tools import TRIP_TOOLS


class TripAgent(BaseAgent):
    """Agent for handling trip management requests."""

    def _define_tools(self) -> list:
        """Return trip tool definitions."""
        return TRIP_TOOLS

    async def _call_function(self, function_name: str, args: dict,
                            user_id: str, trip_id: int) -> dict:
        """Execute trip service calls."""
        trip_service = self.services.get('trip')

        if not trip_service:
            return {"success": False, "error": "Trip service not available"}

        if function_name == "get_current_trip":
            try:
                trip = await trip_service.get_current_trip(user_id)

                if not trip:
                    return {"success": False, "error": "No active trip found"}

                return {"success": True, "trip": trip}
            except Exception as e:
                print(f"Error getting current trip: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "get_all_trips":
            try:
                trips = await trip_service.list_trips(user_id)

                return {"success": True, "trips": trips}
            except Exception as e:
                print(f"Error getting all trips: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "update_trip":
            try:
                # Prepare updates dict (only include provided fields)
                updates = {}
                if "trip_name" in args:
                    updates["trip_name"] = args["trip_name"]
                if "location" in args:
                    updates["location"] = args["location"]
                if "participants" in args:
                    updates["participants"] = args["participants"]

                if not updates:
                    return {"success": False, "error": "No fields to update"}

                # Update trip in database
                result = trip_service.supabase.table('trips')\
                    .update(updates)\
                    .eq('id', trip_id)\
                    .execute()

                if not result.data:
                    return {"success": False, "error": "Failed to update trip"}

                return {"success": True, "trip": result.data[0]}
            except Exception as e:
                print(f"Error updating trip: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"Unknown function: {function_name}"}

    def _format_output(self, function_name: str, output: dict) -> str:
        """Format trip output for user."""
        if not output.get("success"):
            return f"Error: {output.get('error')}"

        if function_name == "get_current_trip":
            trip = output.get("trip", {})
            trip_name = trip.get('trip_name', 'Trip')
            location = trip.get('location', 'Unknown')
            participants = trip.get('participants', [])
            status = trip.get('status', 'active')

            lines = [f"Current Trip: {trip_name}\n"]
            lines.append(f"Destination: {location}")
            lines.append(f"Status: {status.title()}")

            if participants:
                lines.append(f"Participants ({len(participants)}):")
                for participant in participants:
                    lines.append(f"  • {participant}")
            else:
                lines.append("Participants: None")

            return "\n".join(lines)

        elif function_name == "get_all_trips":
            trips = output.get("trips", [])

            if not trips:
                return "You don't have any trips yet. Create a new trip to get started!"

            lines = ["Your Trips:\n"]

            for trip in trips:
                trip_name = trip.get('trip_name', 'Trip')
                location = trip.get('location', 'Unknown')
                status = trip.get('status', 'active')
                participants = trip.get('participants', [])

                # Status emoji
                status_emoji = "🟢" if status == "active" else "⚪"

                trip_line = f"{status_emoji} {trip_name}"
                if location:
                    trip_line += f" - {location}"

                lines.append(trip_line)

                if participants:
                    lines.append(f"   {len(participants)} participant(s): {', '.join(participants[:3])}")
                    if len(participants) > 3:
                        lines.append(f"   ...and {len(participants) - 3} more")

                lines.append("")  # Blank line between trips

            return "\n".join(lines)

        elif function_name == "update_trip":
            trip = output.get("trip", {})
            trip_name = trip.get('trip_name', 'Trip')
            return f"Updated trip '{trip_name}' successfully!"

        return "Done"
