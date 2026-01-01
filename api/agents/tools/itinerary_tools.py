"""Tool definitions for itinerary and schedule operations."""

ITINERARY_TOOLS = [
    {
        "name": "parse_itinerary_text",
        "description": "Parse and extract structured itinerary data from raw pasted text (e.g., user's copy-pasted travel schedule). Use this when the user pastes a schedule/itinerary with dates, times, and activities. This extracts the data and prepares it for saving.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The raw itinerary text pasted by the user"
                }
            },
            "required": ["text"]
        }
    },
    {
        "name": "save_pending_itinerary",
        "description": "Save the previously parsed itinerary to the trip schedule. Use this after parse_itinerary_text when the user confirms they want to save it (e.g., user says 'yes', 'save it', 'do it').",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_itinerary",
        "description": "Get the trip itinerary/schedule for a specific day or all days. Use this when the user asks what's planned, what they're doing on a specific day, or wants to see the schedule.",
        "parameters": {
            "type": "object",
            "properties": {
                "day_number": {
                    "type": "integer",
                    "description": "Specific day number to retrieve (e.g., 2 for 'day 2'). Leave empty to get all days."
                },
                "date": {
                    "type": "string",
                    "description": "Specific date in YYYY-MM-DD format. Leave empty to get all dates."
                }
            }
        }
    },
    {
        "name": "add_itinerary_items",
        "description": "Add new activities to the trip schedule. Use this when the user provides a new itinerary, wants to add activities, or mentions plans for specific days.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of itinerary items to add",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {
                                "type": "string",
                                "description": "Date in YYYY-MM-DD format"
                            },
                            "day_order": {
                                "type": "integer",
                                "description": "Day number (e.g., 1 for day 1, 2 for day 2)"
                            },
                            "time": {
                                "type": "string",
                                "description": "Time in HH:MM format (e.g., '09:30')"
                            },
                            "time_order": {
                                "type": "integer",
                                "description": "Order within the day (1, 2, 3, etc.)"
                            },
                            "title": {
                                "type": "string",
                                "description": "Activity title or name"
                            },
                            "description": {
                                "type": "string",
                                "description": "Optional activity description"
                            },
                            "location": {
                                "type": "string",
                                "description": "Optional location or venue"
                            }
                        },
                        "required": ["title"]
                    }
                },
                "replace_existing": {
                    "type": "boolean",
                    "description": "If true, delete existing itinerary before adding new items. Use when user says 'update itinerary' or 'replace schedule'."
                }
            },
            "required": ["items"]
        }
    },
    {
        "name": "update_itinerary_item",
        "description": "Update a specific itinerary activity. Use this when the user wants to change the time, location, or details of an existing activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "ID of the itinerary item to update (get this from get_itinerary first)"
                },
                "time": {
                    "type": "string",
                    "description": "New time in HH:MM format (optional)"
                },
                "title": {
                    "type": "string",
                    "description": "New activity title (optional)"
                },
                "description": {
                    "type": "string",
                    "description": "New description (optional)"
                },
                "location": {
                    "type": "string",
                    "description": "New location (optional)"
                }
            },
            "required": ["item_id"]
        }
    },
    {
        "name": "delete_itinerary_item",
        "description": "Remove an activity from the schedule. Use this when the user wants to cancel or remove a planned activity.",
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {
                    "type": "integer",
                    "description": "ID of the itinerary item to delete (get this from get_itinerary first)"
                }
            },
            "required": ["item_id"]
        }
    }
]
