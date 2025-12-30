"""PlacesAgent for wishlist places management."""
from api.agents.base_agent import BaseAgent
from api.agents.tools.places_tools import PLACES_TOOLS


class PlacesAgent(BaseAgent):
    """Agent for handling places wishlist requests."""

    def _define_tools(self) -> list:
        """Return places tool definitions."""
        return PLACES_TOOLS

    async def _call_function(self, function_name: str, args: dict,
                            user_id: str, trip_id: int) -> dict:
        """Execute places service calls."""
        places_service = self.services.get('places')

        if not places_service:
            return {"success": False, "error": "Places service not available"}

        if function_name == "add_place":
            try:
                name = args.get("name")
                category = args.get("category")
                notes = args.get("notes")
                google_maps_url = args.get("google_maps_url")

                if not name or not category:
                    return {"success": False, "error": "Name and category are required"}

                # Try to extract place ID from URL if provided
                google_place_id = None
                if google_maps_url:
                    google_place_id = await places_service.extract_place_id_from_url(google_maps_url)

                result = await places_service.add_place(
                    user_id=user_id,
                    trip_id=trip_id,
                    name=name,
                    category=category,
                    google_place_id=google_place_id,
                    google_maps_url=google_maps_url,
                    notes=notes
                )

                return result
            except Exception as e:
                print(f"Error adding place: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "get_places":
            try:
                category = args.get("category")
                visited = args.get("visited")

                places = await places_service.get_trip_places(
                    trip_id=trip_id,
                    category=category,
                    visited=visited
                )

                return {"success": True, "places": places}
            except Exception as e:
                print(f"Error getting places: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "mark_place_visited":
            try:
                place_id = args.get("place_id")
                if not place_id:
                    return {"success": False, "error": "place_id is required"}

                result = await places_service.mark_place_visited(place_id, visited=True)
                return result
            except Exception as e:
                print(f"Error marking place visited: {e}")
                return {"success": False, "error": str(e)}

        elif function_name == "delete_place":
            try:
                place_id = args.get("place_id")
                if not place_id:
                    return {"success": False, "error": "place_id is required"}

                # Delete using Supabase directly
                places_service.supabase.table('trip_places')\
                    .delete()\
                    .eq('id', place_id)\
                    .execute()

                return {"success": True}
            except Exception as e:
                print(f"Error deleting place: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": f"Unknown function: {function_name}"}

    def _format_output(self, function_name: str, output: dict) -> str:
        """Format places output for user."""
        if not output.get("success"):
            return f"Error: {output.get('error')}"

        if function_name == "add_place":
            place = output.get("place", {})
            name = place.get('name', 'Place')
            category = place.get('category', 'other')

            # Category emojis
            emoji_map = {
                'restaurant': '🍴',
                'attraction': '🏛️',
                'shopping': '🛍️',
                'nightlife': '🍺',
                'other': '📍'
            }
            emoji = emoji_map.get(category, '📍')

            response = f"Added to your wishlist: {emoji} {name}"

            # Include rating if available
            rating = place.get('rating')
            if rating:
                response += f" ({rating}⭐)"

            return response

        elif function_name == "get_places":
            places = output.get("places", [])

            if not places:
                return "Your wishlist is empty. Add places you want to visit!"

            # Category emojis
            emoji_map = {
                'restaurant': '🍴',
                'attraction': '🏛️',
                'shopping': '🛍️',
                'nightlife': '🍺',
                'other': '📍'
            }

            # Group by category
            by_category = {}
            for place in places:
                category = place.get('category', 'other')
                if category not in by_category:
                    by_category[category] = []
                by_category[category].append(place)

            lines = ["Your Wishlist:\n"]

            for category, category_places in sorted(by_category.items()):
                emoji = emoji_map.get(category, '📍')
                lines.append(f"{category.title()}:")

                for place in category_places:
                    name = place.get('name', 'Place')
                    visited = place.get('visited', False)
                    rating = place.get('rating')
                    notes = place.get('notes')

                    # Format: "✅ Name (rating)" or "• Name (rating)"
                    check = "✅" if visited else "•"
                    place_line = f"  {check} {name}"

                    if rating:
                        place_line += f" ({rating}⭐)"

                    lines.append(place_line)

                    # Add notes if present
                    if notes:
                        lines.append(f"      {notes}")

                lines.append("")  # Blank line between categories

            return "\n".join(lines)

        elif function_name == "mark_place_visited":
            place = output.get("place", {})
            name = place.get('name', 'Place')
            return f"Marked '{name}' as visited! ✅"

        elif function_name == "delete_place":
            return "Place removed from wishlist."

        return "Done"
