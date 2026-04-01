"""Domain schemas for the Santara knowledge graph entities.

This module defines the core domain models using Pydantic V2 for:
- Graph nodes: Farmer, Market, Region
- Graph relationships: Connected_To, Trades_With
- LLM interaction schemas
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# Enums
# =============================================================================


class AgentStatus(str, Enum):
    """Status of an agent in the simulation."""

    IDLE = "idle"
    THINKING = "thinking"  # Waiting for LLM response
    ACTING = "acting"
    DEAD = "dead"


class CropType(str, Enum):
    """Types of crops that can be grown/traded."""

    RICE = "rice"
    CORN = "corn"
    CASSAVA = "cassava"
    SOYBEAN = "soybean"
    PEANUT = "peanut"
    VEGETABLE = "vegetable"
    FRUIT = "fruit"


class MarketType(str, Enum):
    """Types of markets in the simulation."""

    LOCAL = "local"  # Village-level market
    DISTRICT = "district"  # Kecamatan-level
    REGIONAL = "regional"  # Kabupaten-level


class RelationshipType(str, Enum):
    """Types of relationships between nodes."""

    CONNECTED_TO = "CONNECTED_TO"  # Geographic connection
    TRADES_WITH = "TRADES_WITH"  # Economic relationship
    BELONGS_TO = "BELONGS_TO"  # Farmer belongs to region


# =============================================================================
# Base Models
# =============================================================================


class NodeBase(BaseModel):
    """Base model for all graph nodes."""

    id: UUID = Field(default_factory=uuid4, description="Unique node identifier")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Node creation timestamp",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp",
    )
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional node properties",
    )

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


class RelationshipBase(BaseModel):
    """Base model for all graph relationships."""

    source_id: UUID = Field(description="Source node ID")
    target_id: UUID = Field(description="Target node ID")
    relationship_type: RelationshipType = Field(description="Type of relationship")
    weight: float = Field(default=1.0, ge=0.0, description="Relationship weight/strength")
    properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional relationship properties",
    )

    class Config:
        """Pydantic model configuration."""

        from_attributes = True


# =============================================================================
# Node Models
# =============================================================================


class Farmer(NodeBase):
    """Farmer agent in the simulation.

    Represents an autonomous economic agent that can grow crops,
    trade at markets, and make decisions via LLM reasoning.
    """

    name: str = Field(min_length=1, max_length=100, description="Farmer name")
    region_id: UUID = Field(description="Region this farmer belongs to")
    status: AgentStatus = Field(default=AgentStatus.IDLE, description="Current agent status")

    # Economic attributes
    cash: float = Field(default=0.0, ge=0.0, description="Current cash balance")
    inventory: dict[CropType, float] = Field(
        default_factory=dict,
        description="Crop inventory (type -> quantity in kg)",
    )
    land_size: float = Field(default=1.0, gt=0.0, description="Land size in hectares")

    # Health/survival attributes
    health: float = Field(default=100.0, ge=0.0, le=100.0, description="Health percentage")
    hunger: float = Field(default=0.0, ge=0.0, le=100.0, description="Hunger level")

    # Location
    latitude: float = Field(ge=-90.0, le=90.0, description="Current latitude")
    longitude: float = Field(ge=-180.0, le=180.0, description="Current longitude")


class Market(NodeBase):
    """Market node in the knowledge graph.

    Represents a trading location where farmers can buy/sell crops.
    """

    name: str = Field(min_length=1, max_length=200, description="Market name")
    market_type: MarketType = Field(default=MarketType.LOCAL, description="Market classification")
    region_id: UUID = Field(description="Region this market belongs to")

    # Location
    latitude: float = Field(ge=-90.0, le=90.0, description="Market latitude")
    longitude: float = Field(ge=-180.0, le=180.0, description="Market longitude")

    # Economic attributes
    prices: dict[CropType, float] = Field(
        default_factory=dict,
        description="Current prices per crop type (per kg)",
    )
    demand: dict[CropType, float] = Field(
        default_factory=dict,
        description="Current demand per crop type",
    )
    supply: dict[CropType, float] = Field(
        default_factory=dict,
        description="Current supply per crop type",
    )

    # Capacity
    daily_volume: float = Field(
        default=1000.0,
        gt=0.0,
        description="Maximum daily trading volume in kg",
    )


class Region(NodeBase):
    """Geographic region in the simulation.

    Represents an administrative area containing farmers and markets.
    """

    name: str = Field(min_length=1, max_length=200, description="Region name")
    code: str = Field(min_length=1, max_length=20, description="Administrative code")
    level: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Administrative level (1=province, 2=kabupaten, 3=kecamatan, etc.)",
    )
    parent_id: UUID | None = Field(default=None, description="Parent region ID")

    # Geographic bounds
    center_latitude: float = Field(ge=-90.0, le=90.0, description="Center latitude")
    center_longitude: float = Field(ge=-180.0, le=180.0, description="Center longitude")

    # Statistics
    population: int = Field(default=0, ge=0, description="Population count")
    area_km2: float = Field(default=0.0, ge=0.0, description="Area in square kilometers")


# =============================================================================
# Relationship Models
# =============================================================================


class ConnectedTo(RelationshipBase):
    """Geographic connection between nodes.

    Represents roads, paths, or other physical connections.
    """

    relationship_type: RelationshipType = Field(
        default=RelationshipType.CONNECTED_TO,
        frozen=True,
    )
    distance_km: float = Field(gt=0.0, description="Distance in kilometers")
    travel_time_hours: float = Field(
        default=0.0,
        ge=0.0,
        description="Estimated travel time in hours",
    )
    road_quality: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Road quality score (0=impassable, 1=excellent)",
    )


class TradesWith(RelationshipBase):
    """Economic relationship between a farmer and a market."""

    relationship_type: RelationshipType = Field(
        default=RelationshipType.TRADES_WITH,
        frozen=True,
    )
    frequency: int = Field(
        default=0,
        ge=0,
        description="Number of trades conducted",
    )
    total_volume: float = Field(
        default=0.0,
        ge=0.0,
        description="Total traded volume in kg",
    )
    trust_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Trust/reputation score",
    )


class BelongsTo(RelationshipBase):
    """Membership relationship between a farmer and a region."""

    relationship_type: RelationshipType = Field(
        default=RelationshipType.BELONGS_TO,
        frozen=True,
    )
    since: datetime = Field(
        default_factory=datetime.utcnow,
        description="Membership start date",
    )


# =============================================================================
# LLM Interaction Schemas
# =============================================================================


class AgentContext(BaseModel):
    """Context provided to LLM for agent decision-making.

    This is the "prompt context" sent to the Cloud LLM containing
    the agent's current state and local environment information.
    """

    agent_id: UUID = Field(description="Agent making the decision")
    agent_state: Farmer = Field(description="Current agent state")
    nearby_markets: list[Market] = Field(
        default_factory=list,
        description="Markets within travel range",
    )
    nearby_farmers: list[Farmer] = Field(
        default_factory=list,
        description="Other farmers in the region",
    )
    region: Region | None = Field(default=None, description="Agent's region context")
    current_tick: int = Field(ge=0, description="Current simulation tick")
    weather_conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Current weather data",
    )


class ActionType(str, Enum):
    """Types of actions an agent can take."""

    IDLE = "idle"  # Do nothing
    MOVE = "move"  # Move to a location
    PLANT = "plant"  # Plant crops
    HARVEST = "harvest"  # Harvest crops
    SELL = "sell"  # Sell at market
    BUY = "buy"  # Buy from market
    EAT = "eat"  # Consume food
    REST = "rest"  # Recover health


class ActionDecision(BaseModel):
    """Decision output from LLM for an agent action.

    This schema must match the Protobuf ActionDecision message
    for gRPC communication with the Go simulation engine.
    """

    agent_id: UUID = Field(description="Agent this decision is for")
    action_type: ActionType = Field(description="Type of action to take")
    target_id: UUID | None = Field(
        default=None,
        description="Target entity ID (market, location, etc.)",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters",
    )
    reasoning: str = Field(
        default="",
        max_length=500,
        description="LLM's reasoning for this decision",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score for this decision",
    )

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v: dict[str, Any], info: Any) -> dict[str, Any]:
        """Validate action parameters based on action type."""
        action_type = info.data.get("action_type")
        if action_type == ActionType.SELL and "crop_type" not in v:
            pass  # Optional validation - crop_type recommended but not required
        return v


# =============================================================================
# Graph Summary Models (for LLM context optimization)
# =============================================================================


class CommunityNode(BaseModel):
    """Summarized community node for graph pruning.

    Used to reduce LLM token costs by summarizing neighborhoods.
    """

    community_id: str = Field(description="Community identifier")
    member_count: int = Field(ge=0, description="Number of nodes in community")
    center_latitude: float = Field(ge=-90.0, le=90.0)
    center_longitude: float = Field(ge=-180.0, le=180.0)
    dominant_crops: list[CropType] = Field(
        default_factory=list,
        description="Most common crops in community",
    )
    average_price: dict[CropType, float] = Field(
        default_factory=dict,
        description="Average prices in community",
    )
    summary: str = Field(
        default="",
        max_length=200,
        description="Natural language summary",
    )


class GraphSnapshot(BaseModel):
    """Snapshot of graph state for serialization/caching."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    farmers: list[Farmer] = Field(default_factory=list)
    markets: list[Market] = Field(default_factory=list)
    regions: list[Region] = Field(default_factory=list)
    connections: list[ConnectedTo] = Field(default_factory=list)
    trade_relationships: list[TradesWith] = Field(default_factory=list)
    communities: list[CommunityNode] = Field(default_factory=list)
