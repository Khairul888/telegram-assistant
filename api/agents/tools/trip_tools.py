"""Tool definitions for trip management operations."""

TRIP_TOOLS = [
    {
        "name": "get_current_trip",
        "description": "Get information about the current active trip. Use this when the user asks about their trip, trip details, destination, or participants.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_all_trips",
        "description": "Get a list of all trips for the user. Use this when the user asks to see all their trips or wants to switch trips.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "update_trip",
        "description": "Update trip details like location or participants. Use this when the user wants to change trip information.",
        "parameters": {
            "type": "object",
            "properties": {
                "trip_name": {
                    "type": "string",
                    "description": "New trip name (optional)"
                },
                "location": {
                    "type": "string",
                    "description": "New location or destination (optional)"
                },
                "participants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "New list of participant names (optional)"
                }
            }
        }
    }
]
