"""Orchestrator agent for routing ambiguous requests."""
import json
import re


class OrchestratorAgent:
    """Routes ambiguous messages to appropriate agent using LLM."""

    def __init__(self, gemini_service, services_dict, telegram_utils):
        """
        Initialize orchestrator.

        Args:
            gemini_service: GeminiService instance
            services_dict: Dict of service instances
            telegram_utils: TelegramUtils instance
        """
        self.gemini = gemini_service
        self.services = services_dict
        self.telegram = telegram_utils
        self.agents_map = {
            'expense': 'expense',
            'itinerary': 'itinerary',
            'places': 'places',
            'settlement': 'settlement',
            'trip': 'trip',
            'qa': 'qa'
        }

    async def route(self, user_id: str, chat_id: str, message: str,
                   trip_context: dict) -> dict:
        """
        Route message using LLM classification.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message: User message text
            trip_context: Current trip dict

        Returns:
            dict: {"agent": str, "intent": str}
        """
        prompt = f"""Classify this message and determine which specialized agent should handle it:

Message: "{message}"

Available agents:
- expense: Handle expense tracking, bills, receipts, payments, splits, spending
- itinerary: Handle schedule, itinerary, daily plans, activities, times, day-by-day planning
- places: Handle restaurants, attractions, wishlist, places to visit, Google Maps links
- settlement: Handle balances, who owes whom, settling up, payment calculations
- trip: Handle trip creation, participants, location changes, switching trips
- qa: Handle general questions about the trip (what, when, where, how, weather)

Respond with ONLY the agent name (expense, itinerary, places, settlement, trip, or qa), nothing else."""

        try:
            response = await self.gemini.generate_response(prompt)
            agent_name = response.strip().lower()

            # Validate and clean response
            agent_name = self._clean_agent_name(agent_name)

            if agent_name in self.agents_map:
                return {"agent": agent_name, "intent": message}
            else:
                # Default to QA if invalid response
                print(f"Orchestrator returned invalid agent: {agent_name}, defaulting to qa")
                return {"agent": "qa", "intent": message}

        except Exception as e:
            print(f"Orchestrator error: {e}")
            # Default to QA on error
            return {"agent": "qa", "intent": message}

    def _clean_agent_name(self, agent_name: str) -> str:
        """
        Clean and validate agent name from LLM response.

        Args:
            agent_name: Raw agent name from LLM

        Returns:
            str: Cleaned agent name
        """
        # Remove common prefixes/suffixes
        agent_name = agent_name.strip().lower()
        agent_name = re.sub(r'^(agent|the)\s+', '', agent_name)
        agent_name = re.sub(r'\s+(agent|handler)$', '', agent_name)

        # Extract first word if multiple words
        words = agent_name.split()
        if words:
            agent_name = words[0]

        # Map variations
        variations = {
            'expenses': 'expense',
            'spending': 'expense',
            'costs': 'expense',
            'schedule': 'itinerary',
            'plan': 'itinerary',
            'agenda': 'itinerary',
            'location': 'places',
            'locations': 'places',
            'restaurant': 'places',
            'balance': 'settlement',
            'balances': 'settlement',
            'payment': 'settlement',
            'question': 'qa',
            'questions': 'qa',
            'query': 'qa'
        }

        return variations.get(agent_name, agent_name)
