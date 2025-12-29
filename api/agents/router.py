"""Keyword-based router for fast path routing."""
import re


class KeywordRouter:
    """Routes messages based on keyword patterns."""

    # Keyword patterns for each agent
    PATTERNS = {
        'expense': [
            r'\$\d+',  # Dollar amounts like $15
            r'spent|paid|expense|cost|bill|receipt',
            r'lunch|dinner|breakfast|meal|restaurant|cafe',
            r'add expense|new expense|track expense',
            r'list expenses|show expenses|view expenses',
            r'delete expense|remove expense',
            r'update expense|edit expense|change expense'
        ],
        'itinerary': [
            r'day \d+|day\d+',  # Day references like "day 2"
            r'\d{1,2}:\d{2}',  # Times like 10:30 or 9:00
            r'schedule|itinerary|plan|agenda|activities',
            r'tomorrow|today|morning|afternoon|evening',
            r'move|change.*time|reschedule',
            r'what.*doing|what.*planned',
            r'add.*activity|new activity',
            r'update.*schedule|change.*plan'
        ],
        'places': [
            r'restaurant|place|location|venue',
            r'want to try|check out|visit|go to',
            r'wishlist|places to visit|bucket list',
            r'maps\.google\.com|maps\.app\.goo\.gl|goo\.gl/maps',
            r'add to.*list|save.*place',
            r'mark.*visited|been to|checked off'
        ],
        'settlement': [
            r'balance|owe|owes|debt',
            r'who paid|settle|settlement|pay back|repay',
            r'split|divided|share costs',
            r'calculate.*balance|show.*balance'
        ],
        'trip': [
            r'create trip|new trip|start trip',
            r'participants|add.*participant|remove.*participant',
            r'change location|update location',
            r'switch trip|change trip|select trip',
            r'list trips|show trips|all trips',
            r'current trip|active trip'
        ],
        'qa': [
            r'^(what|when|where|how|why|who|which|can|could|would|should|is|are|do|does)\s',
            r'tell me|explain|describe',
            r'weather|forecast|temperature'
        ]
    }

    def __init__(self, agents: dict, orchestrator):
        """
        Initialize router.

        Args:
            agents: Dict of agent instances {'expense': ExpenseAgent(), ...}
            orchestrator: OrchestratorAgent instance
        """
        self.agents = agents
        self.orchestrator = orchestrator

    async def route(self, user_id: str, chat_id: str, message: str,
                   trip_context: dict) -> dict:
        """
        Route message to appropriate agent.

        Args:
            user_id: Telegram user ID
            chat_id: Telegram chat ID
            message: User message text
            trip_context: Current trip dict

        Returns:
            dict: Agent processing result
        """
        # Try keyword match first (fast path)
        agent_name = self._match_keywords(message)

        if agent_name and agent_name in self.agents:
            agent = self.agents[agent_name]
            try:
                return await agent.process(user_id, chat_id, message, trip_context)
            except Exception as e:
                print(f"Agent {agent_name} error: {e}")
                return {
                    "success": False,
                    "response": f"Agent error: {str(e)}",
                    "already_sent": False
                }

        # Fallback to orchestrator (LLM routing)
        try:
            routing = await self.orchestrator.route(user_id, chat_id, message, trip_context)
            routed_agent_name = routing.get("agent", "qa")

            if routed_agent_name in self.agents:
                agent = self.agents[routed_agent_name]
                return await agent.process(user_id, chat_id, message, trip_context)
            else:
                # Agent not available, return error
                return {
                    "success": False,
                    "response": f"Agent '{routed_agent_name}' not available yet",
                    "already_sent": False
                }
        except Exception as e:
            print(f"Orchestrator error: {e}")
            return {
                "success": False,
                "response": f"Routing error: {str(e)}",
                "already_sent": False
            }

    def _match_keywords(self, message: str) -> str:
        """
        Match message against keyword patterns.

        Args:
            message: User message text

        Returns:
            str: Agent name or None if no match
        """
        message_lower = message.lower()

        # Check each agent's patterns (order matters - more specific first)
        agent_priority = ['expense', 'itinerary', 'places', 'settlement', 'trip', 'qa']

        for agent_name in agent_priority:
            patterns = self.PATTERNS.get(agent_name, [])
            for pattern in patterns:
                if re.search(pattern, message_lower):
                    return agent_name

        return None  # No match, will fallback to orchestrator
