"""Tool definitions for places wishlist operations."""

PLACES_TOOLS = [
    {
        "name": "add_place",
        "description": "Add a place to the trip wishlist. Use this when the user mentions wanting to visit somewhere, try a restaurant, or check out a location.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the place, restaurant, or attraction"
                },
                "category": {
                    "type": "string",
                    "enum": ["restaurant", "attraction", "shopping", "nightlife", "other"],
                    "description": "Category of the place"
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes about the place (e.g., 'famous for ramen', 'recommended by friend')"
                },
                "google_maps_url": {
                    "type": "string",
                    "description": "Google Maps URL if provided by the user"
                }
            },
            "required": ["name", "category"]
        }
    },
    {
        "name": "get_places",
        "description": "Get the wishlist of places to visit. Use this when the user asks to see their wishlist, what places they want to visit, or asks for restaurant recommendations they saved.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["restaurant", "attraction", "shopping", "nightlife", "other"],
                    "description": "Optional: Filter by category"
                },
                "visited": {
                    "type": "boolean",
                    "description": "Optional: Filter by visited status (true for visited, false for not visited)"
                }
            }
        }
    },
    {
        "name": "mark_place_visited",
        "description": "Mark a place as visited. Use this when the user mentions they went to a place or checked it off their list.",
        "parameters": {
            "type": "object",
            "properties": {
                "place_id": {
                    "type": "integer",
                    "description": "ID of the place to mark as visited (get this from get_places first)"
                }
            },
            "required": ["place_id"]
        }
    },
    {
        "name": "delete_place",
        "description": "Remove a place from the wishlist. Use this when the user wants to remove a place they're no longer interested in.",
        "parameters": {
            "type": "object",
            "properties": {
                "place_id": {
                    "type": "integer",
                    "description": "ID of the place to delete (get this from get_places first)"
                }
            },
            "required": ["place_id"]
        }
    }
]
