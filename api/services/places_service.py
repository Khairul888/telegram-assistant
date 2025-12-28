"""Places wishlist service with Google Maps/Places API integration."""
from typing import Dict, List, Optional
import os
import re
import httpx


class PlacesService:
    """Manages trip places wishlist with Google Maps integration."""

    def __init__(self, supabase_client):
        """Initialize with Supabase client."""
        self.supabase = supabase_client
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY')

    async def add_place(self, user_id: str, trip_id: int, name: str,
                       category: str, google_place_id: str = None,
                       google_maps_url: str = None, notes: str = None,
                       priority: str = "medium") -> Dict:
        """
        Add a place to the wishlist, optionally enriching with Google Places data.

        Args:
            user_id: Telegram user ID
            trip_id: Trip ID
            name: Place name
            category: restaurant, attraction, shopping, nightlife, other
            google_place_id: Optional Place ID for enrichment
            google_maps_url: Optional Google Maps URL
            notes: Optional user notes
            priority: low, medium, high

        Returns:
            dict: {"success": bool, "place_id": int, "place": dict} or error
        """
        try:
            place_data = {
                "user_id": user_id,
                "trip_id": trip_id,
                "name": name,
                "category": category,
                "google_maps_url": google_maps_url,
                "notes": notes,
                "priority": priority,
                "source": "detected"
            }

            # If Place ID provided, fetch rich details
            if google_place_id:
                details = await self._fetch_place_details(google_place_id)
                if details:
                    place_data.update({
                        "google_place_id": google_place_id,
                        "address": details.get("formatted_address"),
                        "latitude": details.get("geometry", {}).get("location", {}).get("lat"),
                        "longitude": details.get("geometry", {}).get("location", {}).get("lng"),
                        "rating": details.get("rating"),
                        "user_ratings_total": details.get("user_ratings_total"),
                        "price_level": details.get("price_level"),
                        "phone_number": details.get("formatted_phone_number"),
                        "website": details.get("website"),
                        "opening_hours": details.get("opening_hours"),
                        "photos": details.get("photos", [])[:5],  # Limit to 5 photos
                        "raw_api_data": details,
                        "source": "google_maps"
                    })

            result = self.supabase.table('trip_places').insert(place_data).execute()

            if not result.data:
                return {"success": False, "error": "Failed to add place"}

            place_id = result.data[0]['id']

            return {
                "success": True,
                "place_id": place_id,
                "place": result.data[0]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _fetch_place_details(self, place_id: str) -> Optional[Dict]:
        """
        Fetch place details from Google Places API (New v1).

        Args:
            place_id: Google Place ID

        Returns:
            dict: Place details in legacy format or None on error
        """
        if not self.api_key:
            print("Warning: GOOGLE_MAPS_API_KEY not set")
            return None

        try:
            # Use new Places API v1
            url = f"https://places.googleapis.com/v1/places/{place_id}"

            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "id,displayName,formattedAddress,location,rating,userRatingCount,priceLevel,nationalPhoneNumber,websiteUri,regularOpeningHours,photos"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)

                if response.status_code != 200:
                    print(f"Places API error: {response.status_code} - {response.text}")
                    return None

                data = response.json()

                # Convert new API format to legacy format for compatibility
                legacy_format = {
                    "place_id": data.get("id"),
                    "name": data.get("displayName", {}).get("text"),
                    "formatted_address": data.get("formattedAddress"),
                    "geometry": {
                        "location": {
                            "lat": data.get("location", {}).get("latitude"),
                            "lng": data.get("location", {}).get("longitude")
                        }
                    },
                    "rating": data.get("rating"),
                    "user_ratings_total": data.get("userRatingCount"),
                    "price_level": data.get("priceLevel"),
                    "formatted_phone_number": data.get("nationalPhoneNumber"),
                    "website": data.get("websiteUri"),
                    "opening_hours": data.get("regularOpeningHours"),
                    "photos": data.get("photos", [])
                }

                return legacy_format

        except Exception as e:
            print(f"Error fetching place details: {e}")
            return None

    async def extract_place_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract Google Place ID from various Google Maps URL formats.

        Handles:
        - Short links: https://maps.app.goo.gl/xyz123
        - Long URLs: https://maps.google.com/maps?q=...&ftid=...
        - Place URLs: https://maps.google.com/maps/place/...
        - Embed URLs: https://www.google.com/maps/embed?pb=...

        Args:
            url: Google Maps URL

        Returns:
            str: Place ID or None if not found
        """
        try:
            # Handle short links by following redirect
            if 'maps.app.goo.gl' in url or 'goo.gl' in url:
                async with httpx.AsyncClient(follow_redirects=True) as client:
                    response = await client.get(url, timeout=10.0)
                    url = str(response.url)  # Get final URL after redirect

            # Extract Place ID from various URL patterns
            patterns = [
                r'ftid=(0x[0-9a-f]+:0x[0-9a-f]+)',  # ftid parameter
                r'/place/[^/]+/(0x[0-9a-f]+:0x[0-9a-f]+)',  # In place URL path
                r'!1s(0x[0-9a-f]+:0x[0-9a-f]+)',  # In URL parameters
                r'data=.*!1s(0x[0-9a-f]+:0x[0-9a-f]+)',  # In data parameter
            ]

            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1)

            # If no CID found, try extracting from query parameters
            if '?q=' in url or '&q=' in url:
                match = re.search(r'[?&]q=([^&]+)', url)
                if match:
                    query = match.group(1)
                    # This is a search query, not a Place ID
                    # Could potentially use Places Text Search API here
                    print(f"Found search query: {query} (would need Text Search API)")

            return None

        except Exception as e:
            print(f"Error extracting place ID from URL: {e}")
            return None

    async def get_trip_places(self, trip_id: int, category: str = None,
                             visited: bool = None) -> List[Dict]:
        """
        Get places for a trip, optionally filtered by category and visited status.

        Args:
            trip_id: Trip ID
            category: Optional category filter
            visited: Optional visited status filter

        Returns:
            list: List of place dictionaries
        """
        try:
            query = self.supabase.table('trip_places')\
                .select('*')\
                .eq('trip_id', trip_id)

            if category:
                query = query.eq('category', category)
            if visited is not None:
                query = query.eq('visited', visited)

            result = query.order('created_at', desc=True).execute()

            return result.data if result.data else []
        except Exception as e:
            print(f"Error getting trip places: {e}")
            return []

    async def mark_place_visited(self, place_id: int, visited: bool = True,
                                 visited_date: str = None) -> Dict:
        """
        Mark a place as visited or not visited.

        Args:
            place_id: Place ID
            visited: Visited status
            visited_date: Optional visit date (YYYY-MM-DD)

        Returns:
            dict: {"success": bool, "place": dict} or error
        """
        try:
            update_data = {"visited": visited}
            if visited and visited_date:
                update_data["visited_date"] = visited_date

            result = self.supabase.table('trip_places')\
                .update(update_data)\
                .eq('id', place_id)\
                .execute()

            if not result.data:
                return {"success": False, "error": "Failed to update place"}

            return {"success": True, "place": result.data[0]}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_places_summary(self, trip_id: int) -> Dict:
        """
        Get summary statistics for trip places.

        Args:
            trip_id: Trip ID

        Returns:
            dict: {
                "total_places": int,
                "by_category": dict,
                "visited_count": int,
                "avg_rating": float
            }
        """
        try:
            places = await self.get_trip_places(trip_id)

            if not places:
                return {
                    "total_places": 0,
                    "by_category": {},
                    "visited_count": 0,
                    "avg_rating": None
                }

            # Group by category
            by_category = {}
            for place in places:
                category = place.get('category', 'other')
                by_category[category] = by_category.get(category, 0) + 1

            # Count visited
            visited_count = sum(1 for place in places if place.get('visited'))

            # Calculate average rating
            ratings = [place['rating'] for place in places if place.get('rating')]
            avg_rating = round(sum(ratings) / len(ratings), 1) if ratings else None

            return {
                "total_places": len(places),
                "by_category": by_category,
                "visited_count": visited_count,
                "avg_rating": avg_rating
            }
        except Exception as e:
            print(f"Error getting places summary: {e}")
            return {"total_places": 0, "by_category": {}, "visited_count": 0, "avg_rating": None}
