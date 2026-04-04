"""Graph pruning and community detection for LLM context optimization.

This module implements eager graph pruning strategies to summarize
Neo4j neighborhoods, keeping LLM prompts small to optimize cloud token costs.

Key strategies:
1. Community Detection: Group related nodes into communities
2. Representative Sampling: Select key nodes from each community
3. Context Summarization: Generate natural language summaries
4. Relevance Scoring: Prioritize nodes based on query relevance
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.config import get_locale, LocaleConfig
from src.domain.schemas import (
    AgentContext,
    CommunityNode,
    CropType,
    Farmer,
    Market,
    Region,
)
from src.infrastructure.neo4j_client import Neo4jClient
from src.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PruningConfig:
    """Configuration for graph pruning operations."""

    max_context_nodes: int = 20
    max_nearby_farmers: int = 5
    max_nearby_markets: int = 5
    max_summary_length: int = 200
    community_sample_size: int = 3
    relevance_decay_km: float = 10.0  # Distance decay for relevance scoring


class GraphPruner:
    """Prunes and summarizes graph data for efficient LLM context.

    This class reduces the amount of data sent to Cloud LLMs by:
    1. Detecting communities in the graph
    2. Selecting representative samples from communities
    3. Generating compact summaries
    4. Scoring nodes by relevance to the query agent
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        config: PruningConfig | None = None,
        locale: LocaleConfig | None = None,
    ) -> None:
        """Initialize the graph pruner.

        Args:
            neo4j_client: Connected Neo4j client
            config: Pruning configuration
            locale: Optional locale configuration (defaults to global)
        """
        self._client = neo4j_client
        self._config = config or PruningConfig()
        self._locale = locale or get_locale()
        self._communities_cache: list[CommunityNode] | None = None

    async def build_agent_context(
        self,
        agent: Farmer,
        current_tick: int,
        weather: dict[str, Any] | None = None,
    ) -> AgentContext:
        """Build an optimized context for agent decision-making.

        This method constructs a minimal but sufficient context for
        the LLM to make informed decisions, keeping token costs low.

        Args:
            agent: The agent requiring a decision
            current_tick: Current simulation tick
            weather: Optional weather conditions

        Returns:
            Optimized AgentContext for LLM consumption
        """
        logger.debug("building_agent_context", agent_id=str(agent.id))

        # Get nearby entities
        nearby_markets = await self._get_relevant_markets(agent)
        nearby_farmers = await self._get_relevant_farmers(agent)

        # Get agent's region
        region = await self._client.get_region(agent.region_id)

        # Build context
        context = AgentContext(
            agent_id=agent.id,
            agent_state=agent,
            nearby_markets=nearby_markets,
            nearby_farmers=nearby_farmers,
            region=region,
            current_tick=current_tick,
            weather_conditions=weather or {},
        )

        logger.debug(
            "agent_context_built",
            agent_id=str(agent.id),
            markets_count=len(nearby_markets),
            farmers_count=len(nearby_farmers),
        )

        return context

    async def _get_relevant_markets(self, agent: Farmer) -> list[Market]:
        """Get the most relevant markets for an agent.

        Uses proximity and trade history to score markets.
        """
        # Get nearby markets
        nearby = await self._client.get_markets_nearby(
            latitude=agent.latitude,
            longitude=agent.longitude,
            radius_km=50.0,  # 50km radius
        )

        # Get agent's trade history for relevance scoring
        trade_history = await self._client.get_trade_relationships(agent.id)
        traded_market_ids = {trade.target_id for trade in trade_history}

        # Score and sort markets
        scored_markets: list[tuple[float, Market]] = []
        for market in nearby:
            score = self._calculate_market_relevance(
                agent=agent,
                market=market,
                has_traded=market.id in traded_market_ids,
            )
            scored_markets.append((score, market))

        # Sort by score descending and take top N
        scored_markets.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored_markets[: self._config.max_nearby_markets]]

    async def _get_relevant_farmers(self, agent: Farmer) -> list[Farmer]:
        """Get the most relevant farmers for context.

        Returns other farmers in the same region, excluding dead agents.
        """
        # Get nearby farmers
        nearby = await self._client.get_farmers_nearby(
            latitude=agent.latitude,
            longitude=agent.longitude,
            radius_km=20.0,  # 20km radius for farmers
        )

        # Filter out self and dead agents
        filtered = [
            f
            for f in nearby
            if f.id != agent.id and f.status.value != "dead"
        ]

        # Score by relevance (similar inventory, proximity)
        scored_farmers: list[tuple[float, Farmer]] = []
        for farmer in filtered:
            score = self._calculate_farmer_relevance(agent, farmer)
            scored_farmers.append((score, farmer))

        # Sort and take top N
        scored_farmers.sort(key=lambda x: x[0], reverse=True)
        return [f for _, f in scored_farmers[: self._config.max_nearby_farmers]]

    def _calculate_market_relevance(
        self,
        agent: Farmer,
        market: Market,
        has_traded: bool,
    ) -> float:
        """Calculate relevance score for a market.

        Factors:
        - Distance (closer = more relevant)
        - Trade history (previous trades = more relevant)
        - Price advantage (better prices for agent's inventory = more relevant)
        """
        # Distance factor (exponential decay)
        from math import exp, sqrt

        distance = sqrt(
            (agent.latitude - market.latitude) ** 2
            + (agent.longitude - market.longitude) ** 2
        ) * 111  # Approximate km

        distance_score = exp(-distance / self._config.relevance_decay_km)

        # Trade history bonus
        trade_bonus = 0.3 if has_traded else 0.0

        # Price advantage for agent's inventory
        price_score = 0.0
        for crop, quantity in agent.inventory.items():
            if quantity > 0 and crop in market.prices:
                # Higher price = better for selling
                price_score += market.prices[crop] * 0.00001  # Normalize

        return distance_score + trade_bonus + min(price_score, 0.3)

    def _calculate_farmer_relevance(
        self,
        agent: Farmer,
        other: Farmer,
    ) -> float:
        """Calculate relevance score for another farmer.

        Factors:
        - Distance (closer = more relevant)
        - Inventory similarity (different crops = more interesting)
        - Economic similarity (similar wealth = more comparable)
        """
        from math import exp, sqrt

        # Distance factor
        distance = sqrt(
            (agent.latitude - other.latitude) ** 2
            + (agent.longitude - other.longitude) ** 2
        ) * 111

        distance_score = exp(-distance / 5.0)  # 5km decay for farmers

        # Inventory diversity (different crops = interesting)
        agent_crops = set(agent.inventory.keys())
        other_crops = set(other.inventory.keys())
        diversity_score = len(other_crops - agent_crops) * 0.1

        return distance_score + diversity_score

    async def get_community_summaries(self) -> list[CommunityNode]:
        """Get cached or fresh community summaries.

        Community detection is expensive, so results are cached.
        """
        if self._communities_cache is not None:
            return self._communities_cache

        self._communities_cache = await self._client.detect_communities()
        return self._communities_cache

    def invalidate_cache(self) -> None:
        """Invalidate community cache (call after graph mutations)."""
        self._communities_cache = None

    async def generate_context_summary(
        self,
        context: AgentContext,
    ) -> str:
        """Generate a compact natural language summary of the context.

        This can be used as a system prompt prefix for the LLM.
        """
        parts: list[str] = []

        # Agent state summary
        agent = context.agent_state
        inventory_str = ", ".join(
            f"{crop.value}: {qty:.1f}kg"
            for crop, qty in agent.inventory.items()
            if qty > 0
        ) or "empty"

        parts.append(
            f"Agent {agent.name} is at ({agent.latitude:.4f}, {agent.longitude:.4f}). "
            f"Health: {agent.health:.0f}%, Hunger: {agent.hunger:.0f}%, "
            f"Cash: {self._locale.format_currency(agent.cash)}, Inventory: [{inventory_str}]."
        )

        # Region context
        if context.region:
            parts.append(
                f"Located in {context.region.name} (pop: {context.region.population})."
            )

        # Nearby markets summary
        if context.nearby_markets:
            market_strs = []
            for m in context.nearby_markets[:3]:  # Top 3 only
                best_price = max(m.prices.values()) if m.prices else 0
                market_strs.append(f"{m.name} ({m.market_type.value})")
            parts.append(f"Nearby markets: {', '.join(market_strs)}.")

        # Nearby farmers summary
        if context.nearby_farmers:
            total_neighbors = len(context.nearby_farmers)
            parts.append(f"{total_neighbors} other farmers nearby.")

        # Weather
        if context.weather_conditions:
            weather = context.weather_conditions
            parts.append(f"Weather: {weather.get('condition', 'clear')}.")

        summary = " ".join(parts)

        # Truncate if too long
        if len(summary) > self._config.max_summary_length:
            summary = summary[: self._config.max_summary_length - 3] + "..."

        return summary

    async def prune_for_batch_reasoning(
        self,
        agents: list[Farmer],
        current_tick: int,
    ) -> dict[UUID, AgentContext]:
        """Build contexts for multiple agents efficiently.

        Uses batch queries and shared community data.

        Args:
            agents: List of agents needing decisions
            current_tick: Current simulation tick

        Returns:
            Mapping of agent ID to their context
        """
        logger.info("batch_context_building", agent_count=len(agents))

        # Pre-fetch communities for all agents
        await self.get_community_summaries()

        # Build contexts in parallel (could use asyncio.gather for true parallelism)
        contexts: dict[UUID, AgentContext] = {}
        for agent in agents:
            contexts[agent.id] = await self.build_agent_context(
                agent=agent,
                current_tick=current_tick,
            )

        return contexts


# =============================================================================
# Helper Functions
# =============================================================================


def estimate_token_count(context: AgentContext) -> int:
    """Estimate the number of tokens in a context.

    Rough estimation: ~4 characters per token for JSON.
    """
    import json

    # Serialize to JSON and estimate
    json_str = context.model_dump_json()
    return len(json_str) // 4


def should_refresh_communities(
    last_refresh_tick: int,
    current_tick: int,
    refresh_interval: int = 100,
) -> bool:
    """Determine if community cache should be refreshed."""
    return (current_tick - last_refresh_tick) >= refresh_interval
