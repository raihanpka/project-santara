"""Domain repository interfaces.

Following Clean Architecture, these interfaces are defined in the domain layer
and implemented by adapters in the infrastructure layer. This ensures the domain
remains pure and independent of external dependencies.
"""

from abc import ABC, abstractmethod
from typing import Protocol
from uuid import UUID

from src.domain.schemas import (
    CommunityNode,
    ConnectedTo,
    Farmer,
    GraphSnapshot,
    Market,
    Region,
    TradesWith,
)


class FarmerRepository(Protocol):
    """Repository interface for Farmer entities."""

    async def get_by_id(self, farmer_id: UUID) -> Farmer | None:
        """Get a farmer by ID."""
        ...

    async def get_by_region(self, region_id: UUID) -> list[Farmer]:
        """Get all farmers in a region."""
        ...

    async def get_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[Farmer]:
        """Get farmers within a radius of a location."""
        ...

    async def create(self, farmer: Farmer) -> Farmer:
        """Create a new farmer."""
        ...

    async def update(self, farmer: Farmer) -> Farmer:
        """Update an existing farmer."""
        ...

    async def delete(self, farmer_id: UUID) -> bool:
        """Delete a farmer by ID."""
        ...


class MarketRepository(Protocol):
    """Repository interface for Market entities."""

    async def get_by_id(self, market_id: UUID) -> Market | None:
        """Get a market by ID."""
        ...

    async def get_by_region(self, region_id: UUID) -> list[Market]:
        """Get all markets in a region."""
        ...

    async def get_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[Market]:
        """Get markets within a radius of a location."""
        ...

    async def create(self, market: Market) -> Market:
        """Create a new market."""
        ...

    async def update(self, market: Market) -> Market:
        """Update an existing market."""
        ...

    async def delete(self, market_id: UUID) -> bool:
        """Delete a market by ID."""
        ...


class RegionRepository(Protocol):
    """Repository interface for Region entities."""

    async def get_by_id(self, region_id: UUID) -> Region | None:
        """Get a region by ID."""
        ...

    async def get_by_code(self, code: str) -> Region | None:
        """Get a region by administrative code."""
        ...

    async def get_children(self, parent_id: UUID) -> list[Region]:
        """Get child regions of a parent region."""
        ...

    async def get_all(self, level: int | None = None) -> list[Region]:
        """Get all regions, optionally filtered by level."""
        ...

    async def create(self, region: Region) -> Region:
        """Create a new region."""
        ...

    async def update(self, region: Region) -> Region:
        """Update an existing region."""
        ...


class GraphRepository(Protocol):
    """Repository interface for graph-level operations."""

    async def get_connections(self, node_id: UUID) -> list[ConnectedTo]:
        """Get all connections from a node."""
        ...

    async def get_trade_relationships(self, farmer_id: UUID) -> list[TradesWith]:
        """Get all trade relationships for a farmer."""
        ...

    async def create_connection(self, connection: ConnectedTo) -> ConnectedTo:
        """Create a geographic connection between nodes."""
        ...

    async def create_trade_relationship(self, trade: TradesWith) -> TradesWith:
        """Create or update a trade relationship."""
        ...

    async def get_communities(self) -> list[CommunityNode]:
        """Get summarized community nodes for LLM context."""
        ...

    async def get_snapshot(self) -> GraphSnapshot:
        """Get a full graph snapshot."""
        ...

    async def apply_schema_constraints(self) -> None:
        """Apply database schema constraints and indexes."""
        ...


class LLMClient(ABC):
    """Abstract base class for LLM client implementations.

    Defines the contract for Cloud LLM integrations with
    rate limiting and retry capabilities.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a text response from the LLM.

        Args:
            prompt: User prompt to send
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response

        Returns:
            Generated text response

        Raises:
            LLMError: If the request fails after retries
        """
        ...

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: type,
        system_prompt: str | None = None,
    ) -> dict:
        """Generate a structured JSON response matching a schema.

        Args:
            prompt: User prompt to send
            response_schema: Pydantic model or JSON schema for response
            system_prompt: Optional system prompt

        Returns:
            Parsed response matching the schema

        Raises:
            LLMError: If the request fails or response doesn't match schema
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the client and release resources."""
        ...


# =============================================================================
# Domain Errors
# =============================================================================


class DomainError(Exception):
    """Base exception for domain errors."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR") -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class EntityNotFoundError(DomainError):
    """Entity not found in repository."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_type} with ID {entity_id} not found",
            code="ENTITY_NOT_FOUND",
        )


class InvalidStateError(DomainError):
    """Invalid state transition or operation."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, code="INVALID_STATE")


class LLMError(DomainError):
    """Error from LLM service."""

    def __init__(self, message: str, provider: str, original_error: Exception | None = None) -> None:
        self.provider = provider
        self.original_error = original_error
        super().__init__(message=message, code="LLM_ERROR")


class RateLimitError(LLMError):
    """Rate limit exceeded on LLM service."""

    def __init__(self, provider: str, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        super().__init__(
            message=f"Rate limit exceeded for {provider}",
            provider=provider,
        )


class GraphConnectionError(DomainError):
    """Error connecting to graph database."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        self.original_error = original_error
        super().__init__(message=message, code="GRAPH_CONNECTION_ERROR")
