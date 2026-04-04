"""Agent tools for LLM function calling.

This module defines the exact Python functions that the Cloud LLM can call
during agent decision-making. These tools provide real-time access to:
- Market prices and conditions
- Agent inventory and state
- Geographic information
- Trade history

Each tool is designed to be called by the LLM to gather information
needed for decision-making, following the Agentic RAG pattern.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.config import get_locale, LocaleConfig
from src.domain.schemas import CropType, Farmer, Market
from src.infrastructure.neo4j_client import Neo4jClient
from src.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ToolResult:
    """Result from executing a tool."""

    success: bool
    data: Any
    error: str | None = None


class AgentTools:
    """Tools available to the LLM for agent decision-making.

    These tools implement the "function calling" pattern where the LLM
    can request specific information during reasoning. Each tool:
    1. Validates input parameters
    2. Queries the appropriate data source
    3. Returns formatted, locale-aware results
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        locale: LocaleConfig | None = None,
    ) -> None:
        """Initialize agent tools.

        Args:
            neo4j_client: Connected Neo4j client
            locale: Optional locale configuration
        """
        self._neo4j = neo4j_client
        self._locale = locale or get_locale()

    # =========================================================================
    # Price and Market Tools
    # =========================================================================

    async def get_local_price(
        self,
        crop_type: str,
        latitude: float,
        longitude: float,
        radius_km: float = 20.0,
    ) -> ToolResult:
        """Get the average local price for a crop type.

        This tool queries nearby markets to find the current average price
        for a specific crop, helping agents make selling decisions.

        Args:
            crop_type: Type of crop (e.g., "rice", "corn")
            latitude: Agent's current latitude
            longitude: Agent's current longitude
            radius_km: Search radius in kilometers

        Returns:
            ToolResult with price data or error
        """
        try:
            # Validate crop type
            try:
                crop = CropType(crop_type.lower())
            except ValueError:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Invalid crop type: {crop_type}. Valid types: {[c.value for c in CropType]}",
                )

            # Get nearby markets
            markets = await self._neo4j.get_markets_nearby(
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
            )

            if not markets:
                return ToolResult(
                    success=True,
                    data={
                        "crop_type": crop.value,
                        "average_price": None,
                        "min_price": None,
                        "max_price": None,
                        "markets_found": 0,
                        "message": "No markets found within search radius",
                    },
                )

            # Calculate price statistics
            prices = [m.prices.get(crop, 0) for m in markets if crop in m.prices]

            if not prices:
                return ToolResult(
                    success=True,
                    data={
                        "crop_type": crop.value,
                        "average_price": None,
                        "min_price": None,
                        "max_price": None,
                        "markets_found": len(markets),
                        "message": f"No markets selling {crop.value} found",
                    },
                )

            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)

            return ToolResult(
                success=True,
                data={
                    "crop_type": crop.value,
                    "average_price": avg_price,
                    "average_price_formatted": self._locale.format_currency(avg_price),
                    "min_price": min_price,
                    "min_price_formatted": self._locale.format_currency(min_price),
                    "max_price": max_price,
                    "max_price_formatted": self._locale.format_currency(max_price),
                    "markets_found": len(markets),
                    "markets_with_crop": len(prices),
                },
            )

        except Exception as e:
            logger.error("get_local_price_error", error=str(e))
            return ToolResult(success=False, data=None, error=str(e))

    async def get_market_info(
        self,
        market_id: str,
    ) -> ToolResult:
        """Get detailed information about a specific market.

        Args:
            market_id: UUID of the market

        Returns:
            ToolResult with market data or error
        """
        try:
            market_uuid = UUID(market_id)
            market = await self._neo4j.get_market(market_uuid)

            if not market:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Market not found: {market_id}",
                )

            # Format prices with locale
            formatted_prices = {
                crop.value: {
                    "price": price,
                    "formatted": self._locale.format_currency(price),
                }
                for crop, price in market.prices.items()
            }

            return ToolResult(
                success=True,
                data={
                    "id": str(market.id),
                    "name": market.name,
                    "market_type": market.market_type.value,
                    "location": {
                        "latitude": market.latitude,
                        "longitude": market.longitude,
                    },
                    "prices": formatted_prices,
                    "daily_volume": market.daily_volume,
                },
            )

        except ValueError:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid market ID format: {market_id}",
            )
        except Exception as e:
            logger.error("get_market_info_error", error=str(e))
            return ToolResult(success=False, data=None, error=str(e))

    async def find_best_market(
        self,
        crop_type: str,
        latitude: float,
        longitude: float,
        radius_km: float = 50.0,
    ) -> ToolResult:
        """Find the best market to sell a specific crop.

        Considers both price and distance to recommend the optimal market.

        Args:
            crop_type: Type of crop to sell
            latitude: Agent's current latitude
            longitude: Agent's current longitude
            radius_km: Maximum search radius

        Returns:
            ToolResult with best market recommendation
        """
        try:
            # Validate crop type
            try:
                crop = CropType(crop_type.lower())
            except ValueError:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Invalid crop type: {crop_type}",
                )

            # Get nearby markets
            markets = await self._neo4j.get_markets_nearby(
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
            )

            if not markets:
                return ToolResult(
                    success=True,
                    data={"best_market": None, "message": "No markets found"},
                )

            # Score markets by price and distance
            from math import sqrt

            scored_markets: list[tuple[float, Market, float, float]] = []
            for market in markets:
                if crop not in market.prices:
                    continue

                price = market.prices[crop]
                distance = sqrt(
                    (latitude - market.latitude) ** 2
                    + (longitude - market.longitude) ** 2
                ) * 111  # Approximate km

                # Score: higher price is better, closer is better
                # Normalize: assume max price ~50000, max distance ~50km
                price_score = price / 50000
                distance_score = 1 - (distance / radius_km)
                total_score = price_score * 0.7 + distance_score * 0.3

                scored_markets.append((total_score, market, price, distance))

            if not scored_markets:
                return ToolResult(
                    success=True,
                    data={
                        "best_market": None,
                        "message": f"No markets found selling {crop.value}",
                    },
                )

            # Sort by score descending
            scored_markets.sort(key=lambda x: x[0], reverse=True)
            best = scored_markets[0]

            return ToolResult(
                success=True,
                data={
                    "best_market": {
                        "id": str(best[1].id),
                        "name": best[1].name,
                        "price": best[2],
                        "price_formatted": self._locale.format_currency(best[2]),
                        "distance_km": round(best[3], 2),
                        "score": round(best[0], 3),
                    },
                    "alternatives": [
                        {
                            "id": str(m.id),
                            "name": m.name,
                            "price": p,
                            "distance_km": round(d, 2),
                        }
                        for _, m, p, d in scored_markets[1:4]  # Top 3 alternatives
                    ],
                },
            )

        except Exception as e:
            logger.error("find_best_market_error", error=str(e))
            return ToolResult(success=False, data=None, error=str(e))

    # =========================================================================
    # Inventory and Agent Tools
    # =========================================================================

    async def check_inventory(
        self,
        agent_id: str,
    ) -> ToolResult:
        """Check an agent's current inventory.

        Args:
            agent_id: UUID of the agent

        Returns:
            ToolResult with inventory data
        """
        try:
            agent_uuid = UUID(agent_id)
            agent = await self._neo4j.get_farmer(agent_uuid)

            if not agent:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Agent not found: {agent_id}",
                )

            # Format inventory
            inventory_items = [
                {
                    "crop": crop.value,
                    "quantity_kg": qty,
                    "quantity_formatted": f"{qty:.1f}kg",
                }
                for crop, qty in agent.inventory.items()
                if qty > 0
            ]

            total_weight = sum(item["quantity_kg"] for item in inventory_items)

            return ToolResult(
                success=True,
                data={
                    "agent_id": agent_id,
                    "items": inventory_items,
                    "total_items": len(inventory_items),
                    "total_weight_kg": round(total_weight, 2),
                    "is_empty": len(inventory_items) == 0,
                },
            )

        except ValueError:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid agent ID format: {agent_id}",
            )
        except Exception as e:
            logger.error("check_inventory_error", error=str(e))
            return ToolResult(success=False, data=None, error=str(e))

    async def get_agent_status(
        self,
        agent_id: str,
    ) -> ToolResult:
        """Get the current status of an agent.

        Args:
            agent_id: UUID of the agent

        Returns:
            ToolResult with agent status
        """
        try:
            agent_uuid = UUID(agent_id)
            agent = await self._neo4j.get_farmer(agent_uuid)

            if not agent:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Agent not found: {agent_id}",
                )

            # Assess agent needs
            needs_food = agent.hunger > 60
            needs_rest = agent.health < 40
            has_inventory = any(qty > 0 for qty in agent.inventory.values())

            return ToolResult(
                success=True,
                data={
                    "agent_id": agent_id,
                    "name": agent.name,
                    "status": agent.status.value,
                    "health": round(agent.health, 1),
                    "hunger": round(agent.hunger, 1),
                    "cash": agent.cash,
                    "cash_formatted": self._locale.format_currency(agent.cash),
                    "location": {
                        "latitude": agent.latitude,
                        "longitude": agent.longitude,
                    },
                    "land_size_ha": agent.land_size,
                    "needs_food": needs_food,
                    "needs_rest": needs_rest,
                    "has_inventory": has_inventory,
                },
            )

        except ValueError:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid agent ID format: {agent_id}",
            )
        except Exception as e:
            logger.error("get_agent_status_error", error=str(e))
            return ToolResult(success=False, data=None, error=str(e))

    # =========================================================================
    # Trade History Tools
    # =========================================================================

    async def get_trade_history(
        self,
        agent_id: str,
        limit: int = 10,
    ) -> ToolResult:
        """Get an agent's recent trade history.

        Args:
            agent_id: UUID of the agent
            limit: Maximum number of trades to return

        Returns:
            ToolResult with trade history
        """
        try:
            agent_uuid = UUID(agent_id)
            trades = await self._neo4j.get_trade_relationships(agent_uuid)

            # Sort by frequency/weight and limit
            trades = sorted(trades, key=lambda t: t.weight, reverse=True)[:limit]

            trade_list = []
            for trade in trades:
                trade_list.append({
                    "market_id": str(trade.target_id),
                    "frequency": trade.frequency if hasattr(trade, "frequency") else 0,
                    "total_volume": trade.total_volume if hasattr(trade, "total_volume") else 0,
                    "trust_score": trade.trust_score if hasattr(trade, "trust_score") else 0.5,
                })

            return ToolResult(
                success=True,
                data={
                    "agent_id": agent_id,
                    "trades": trade_list,
                    "total_relationships": len(trade_list),
                },
            )

        except ValueError:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid agent ID format: {agent_id}",
            )
        except Exception as e:
            logger.error("get_trade_history_error", error=str(e))
            return ToolResult(success=False, data=None, error=str(e))

    # =========================================================================
    # Geographic Tools
    # =========================================================================

    async def get_region_info(
        self,
        region_id: str,
    ) -> ToolResult:
        """Get information about a region.

        Args:
            region_id: UUID of the region

        Returns:
            ToolResult with region data
        """
        try:
            region_uuid = UUID(region_id)
            region = await self._neo4j.get_region(region_uuid)

            if not region:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"Region not found: {region_id}",
                )

            level_name = self._locale.get_admin_level_name(region.level)

            return ToolResult(
                success=True,
                data={
                    "id": str(region.id),
                    "name": region.name,
                    "code": region.code,
                    "level": region.level,
                    "level_name": level_name,
                    "population": region.population,
                    "area_km2": region.area_km2,
                    "center": {
                        "latitude": region.center_latitude,
                        "longitude": region.center_longitude,
                    },
                },
            )

        except ValueError:
            return ToolResult(
                success=False,
                data=None,
                error=f"Invalid region ID format: {region_id}",
            )
        except Exception as e:
            logger.error("get_region_info_error", error=str(e))
            return ToolResult(success=False, data=None, error=str(e))

    async def calculate_travel_time(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        speed_km_per_tick: float = 0.5,
    ) -> ToolResult:
        """Calculate estimated travel time between two locations.

        Args:
            from_lat: Starting latitude
            from_lon: Starting longitude
            to_lat: Destination latitude
            to_lon: Destination longitude
            speed_km_per_tick: Travel speed in km per tick

        Returns:
            ToolResult with travel time estimate
        """
        try:
            from math import sqrt

            # Calculate distance (simplified Euclidean * 111 for km)
            distance_km = sqrt(
                (to_lat - from_lat) ** 2 + (to_lon - from_lon) ** 2
            ) * 111

            # Calculate ticks needed
            ticks_needed = int(distance_km / speed_km_per_tick) + 1

            return ToolResult(
                success=True,
                data={
                    "distance_km": round(distance_km, 2),
                    "estimated_ticks": ticks_needed,
                    "speed_km_per_tick": speed_km_per_tick,
                },
            )

        except Exception as e:
            logger.error("calculate_travel_time_error", error=str(e))
            return ToolResult(success=False, data=None, error=str(e))


# =============================================================================
# Tool Definitions for LLM
# =============================================================================

TOOL_DEFINITIONS = [
    {
        "name": "get_local_price",
        "description": "Get the average local price for a crop type within a radius of the agent's location",
        "parameters": {
            "type": "object",
            "properties": {
                "crop_type": {
                    "type": "string",
                    "description": "Type of crop (rice, corn, cassava, soybean, peanut, vegetable, fruit)",
                },
                "latitude": {
                    "type": "number",
                    "description": "Agent's current latitude",
                },
                "longitude": {
                    "type": "number",
                    "description": "Agent's current longitude",
                },
                "radius_km": {
                    "type": "number",
                    "description": "Search radius in kilometers (default: 20)",
                },
            },
            "required": ["crop_type", "latitude", "longitude"],
        },
    },
    {
        "name": "get_market_info",
        "description": "Get detailed information about a specific market including prices and location",
        "parameters": {
            "type": "object",
            "properties": {
                "market_id": {
                    "type": "string",
                    "description": "UUID of the market",
                },
            },
            "required": ["market_id"],
        },
    },
    {
        "name": "find_best_market",
        "description": "Find the best market to sell a specific crop, considering both price and distance",
        "parameters": {
            "type": "object",
            "properties": {
                "crop_type": {
                    "type": "string",
                    "description": "Type of crop to sell",
                },
                "latitude": {
                    "type": "number",
                    "description": "Agent's current latitude",
                },
                "longitude": {
                    "type": "number",
                    "description": "Agent's current longitude",
                },
                "radius_km": {
                    "type": "number",
                    "description": "Maximum search radius (default: 50)",
                },
            },
            "required": ["crop_type", "latitude", "longitude"],
        },
    },
    {
        "name": "check_inventory",
        "description": "Check an agent's current inventory of crops",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "UUID of the agent",
                },
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "get_agent_status",
        "description": "Get the current status of an agent including health, hunger, and cash",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "UUID of the agent",
                },
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "get_trade_history",
        "description": "Get an agent's recent trade history with markets",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "string",
                    "description": "UUID of the agent",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of trades to return (default: 10)",
                },
            },
            "required": ["agent_id"],
        },
    },
    {
        "name": "get_region_info",
        "description": "Get information about a geographic region",
        "parameters": {
            "type": "object",
            "properties": {
                "region_id": {
                    "type": "string",
                    "description": "UUID of the region",
                },
            },
            "required": ["region_id"],
        },
    },
    {
        "name": "calculate_travel_time",
        "description": "Calculate estimated travel time between two locations",
        "parameters": {
            "type": "object",
            "properties": {
                "from_lat": {
                    "type": "number",
                    "description": "Starting latitude",
                },
                "from_lon": {
                    "type": "number",
                    "description": "Starting longitude",
                },
                "to_lat": {
                    "type": "number",
                    "description": "Destination latitude",
                },
                "to_lon": {
                    "type": "number",
                    "description": "Destination longitude",
                },
            },
            "required": ["from_lat", "from_lon", "to_lat", "to_lon"],
        },
    },
]
