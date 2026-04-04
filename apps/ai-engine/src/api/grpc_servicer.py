"""gRPC server implementation for the Python AI Engine (Inference Gateway).

This module implements the InferenceService defined in simulation.proto,
providing the interface for the Go Simulation Engine to request agent decisions.

The service handles:
1. Single agent decision requests (GetDecision)
2. Batch decision requests (GetBatchDecisions)
3. Health checks

Architecture:
- Go Engine calls this service when agents need complex reasoning
- This service queries Neo4j, calls Cloud LLM, returns ActionDecision
- Uses the AgenticRAG system for context building and decision generation
"""

import asyncio
from concurrent import futures
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from src.config import get_settings
from src.domain.schemas import (
    ActionDecision,
    ActionType,
    AgentStatus,
    CropType,
    Farmer,
    Market,
)
from src.infrastructure.cloud_llm_client import create_llm_router
from src.infrastructure.neo4j_client import create_neo4j_client
from src.logging import get_logger
from src.usecases.agentic_rag import AgenticRAG

logger = get_logger(__name__)

# The generated protobuf modules will be imported after running `make proto`
# For now, we define placeholder types that match the proto definitions
# In production, replace with:
# from libs.rpc_contracts.gen.python import simulation_pb2, simulation_pb2_grpc


class InferenceServicer:
    """Implements the InferenceService gRPC interface.

    This is the Python-side implementation that Go calls to get agent decisions.
    """

    def __init__(
        self,
        agentic_rag: AgenticRAG,
    ) -> None:
        """Initialize the servicer.

        Args:
            agentic_rag: Initialized AgenticRAG system
        """
        self._rag = agentic_rag
        self._request_count = 0
        self._error_count = 0

    async def GetDecision(
        self,
        request: Any,  # GetDecisionRequest from proto
        context: grpc.aio.ServicerContext,
    ) -> Any:  # GetDecisionResponse
        """Get a decision for a single agent.

        Args:
            request: GetDecisionRequest containing agent state
            context: gRPC context

        Returns:
            GetDecisionResponse with ActionDecision
        """
        self._request_count += 1
        request_id = self._request_count

        logger.info(
            "grpc_get_decision_start",
            request_id=request_id,
            agent_id=request.agent.id if hasattr(request, "agent") else "unknown",
        )

        try:
            # Convert proto AgentState to domain Farmer
            agent = proto_to_farmer(request.agent)

            # Extract weather conditions
            weather = None
            if hasattr(request, "weather") and request.weather:
                weather = {
                    "condition": request.weather.condition,
                    "temperature": request.weather.temperature_celsius,
                    "humidity": request.weather.humidity_percent,
                    "rainfall": request.weather.rainfall_mm,
                    "season": request.weather.season,
                }

            # Generate decision using AgenticRAG
            decision = await self._rag.decide(
                agent=agent,
                current_tick=request.current_tick,
                weather=weather,
            )

            # Convert domain ActionDecision to proto
            proto_decision = decision_to_proto(decision)

            logger.info(
                "grpc_get_decision_complete",
                request_id=request_id,
                agent_id=str(agent.id),
                action=decision.action_type.value,
            )

            # Build response
            # In production with generated stubs:
            # return simulation_pb2.GetDecisionResponse(
            #     decision=proto_decision,
            #     context_summary=decision.reasoning,
            # )
            return {
                "decision": proto_decision,
                "context_summary": decision.reasoning,
            }

        except Exception as e:
            self._error_count += 1
            logger.error(
                "grpc_get_decision_error",
                request_id=request_id,
                error=str(e),
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise

    async def GetBatchDecisions(
        self,
        request: Any,  # GetBatchDecisionsRequest from proto
        context: grpc.aio.ServicerContext,
    ) -> Any:  # GetBatchDecisionsResponse
        """Get decisions for multiple agents in batch.

        Args:
            request: GetBatchDecisionsRequest containing agent states
            context: gRPC context

        Returns:
            GetBatchDecisionsResponse with decisions map
        """
        self._request_count += 1
        request_id = self._request_count
        agent_count = len(request.agents) if hasattr(request, "agents") else 0

        logger.info(
            "grpc_batch_decision_start",
            request_id=request_id,
            agent_count=agent_count,
        )

        try:
            # Convert proto agents to domain
            agents = [proto_to_farmer(a) for a in request.agents]

            # Extract weather
            weather = None
            if hasattr(request, "weather") and request.weather:
                weather = {
                    "condition": request.weather.condition,
                    "temperature": request.weather.temperature_celsius,
                    "humidity": request.weather.humidity_percent,
                    "rainfall": request.weather.rainfall_mm,
                    "season": request.weather.season,
                }

            # Generate batch decisions
            decisions = await self._rag.decide_batch(
                agents=agents,
                current_tick=request.current_tick,
                weather=weather,
            )

            # Convert to proto format
            proto_decisions = {
                str(agent_id): decision_to_proto(decision)
                for agent_id, decision in decisions.items()
            }

            logger.info(
                "grpc_batch_decision_complete",
                request_id=request_id,
                agent_count=agent_count,
                decisions_count=len(decisions),
            )

            # In production with generated stubs:
            # return simulation_pb2.GetBatchDecisionsResponse(
            #     decisions=proto_decisions,
            #     total_requested=agent_count,
            #     total_successful=len(decisions),
            # )
            return {
                "decisions": proto_decisions,
                "total_requested": agent_count,
                "total_successful": len(decisions),
            }

        except Exception as e:
            self._error_count += 1
            logger.error(
                "grpc_batch_decision_error",
                request_id=request_id,
                error=str(e),
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            raise

    async def HealthCheck(
        self,
        request: Any,  # HealthCheckRequest from proto
        context: grpc.aio.ServicerContext,
    ) -> Any:  # HealthCheckResponse
        """Check service health.

        Returns:
            HealthCheckResponse with health status
        """
        # In production with generated stubs:
        # return simulation_pb2.HealthCheckResponse(
        #     healthy=True,
        #     version="0.1.0",
        #     service_name="ai-engine",
        # )
        return {
            "healthy": True,
            "version": "0.1.0",
            "service_name": "ai-engine",
        }

    def get_stats(self) -> dict[str, int]:
        """Get service statistics."""
        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
        }


# =============================================================================
# Proto Conversion Functions
# =============================================================================


def proto_to_farmer(proto_agent: Any) -> Farmer:
    """Convert a proto AgentState to domain Farmer.

    Args:
        proto_agent: Proto AgentState message

    Returns:
        Domain Farmer instance
    """
    # Map proto status enum to domain enum
    status_map = {
        0: AgentStatus.IDLE,  # UNSPECIFIED
        1: AgentStatus.IDLE,
        2: AgentStatus.THINKING,
        3: AgentStatus.ACTING,
        4: AgentStatus.DEAD,
    }

    # Map proto crop types to domain
    crop_type_map = {
        1: CropType.RICE,
        2: CropType.CORN,
        3: CropType.CASSAVA,
        4: CropType.SOYBEAN,
        5: CropType.PEANUT,
        6: CropType.VEGETABLE,
        7: CropType.FRUIT,
    }

    # Parse inventory
    inventory: dict[CropType, float] = {}
    if hasattr(proto_agent, "inventory") and proto_agent.inventory:
        items = proto_agent.inventory.items if hasattr(proto_agent.inventory, "items") else {}
        for crop_enum, quantity in items.items():
            if crop_enum in crop_type_map:
                inventory[crop_type_map[crop_enum]] = quantity

    # Parse location
    latitude = 0.0
    longitude = 0.0
    if hasattr(proto_agent, "location") and proto_agent.location:
        latitude = proto_agent.location.latitude
        longitude = proto_agent.location.longitude

    return Farmer(
        id=UUID(proto_agent.id) if proto_agent.id else UUID("00000000-0000-0000-0000-000000000000"),
        name=proto_agent.name or "Unknown",
        region_id=UUID(proto_agent.region_id) if proto_agent.region_id else UUID("00000000-0000-0000-0000-000000000000"),
        status=status_map.get(proto_agent.status, AgentStatus.IDLE),
        cash=proto_agent.cash or 0.0,
        inventory=inventory,
        land_size=proto_agent.land_size or 1.0,
        health=proto_agent.health or 100.0,
        hunger=proto_agent.hunger or 0.0,
        latitude=latitude,
        longitude=longitude,
    )


def decision_to_proto(decision: ActionDecision) -> dict[str, Any]:
    """Convert a domain ActionDecision to proto format.

    Args:
        decision: Domain ActionDecision

    Returns:
        Dict representation matching proto ActionDecision
    """
    # Map domain action types to proto enum values
    action_type_map = {
        ActionType.IDLE: 1,
        ActionType.MOVE: 2,
        ActionType.PLANT: 3,
        ActionType.HARVEST: 4,
        ActionType.SELL: 5,
        ActionType.BUY: 6,
        ActionType.EAT: 7,
        ActionType.REST: 8,
    }

    # Convert parameters to string map (proto uses map<string, string>)
    params = {str(k): str(v) for k, v in decision.parameters.items()}

    now = datetime.now(timezone.utc)

    return {
        "agent_id": str(decision.agent_id),
        "action_type": action_type_map.get(decision.action_type, 1),
        "target_id": str(decision.target_id) if decision.target_id else "",
        "parameters": params,
        "reasoning": decision.reasoning,
        "confidence": decision.confidence,
        "tick": 0,  # Will be set by caller
        "decided_at": now.isoformat(),
    }


def farmer_to_proto(farmer: Farmer) -> dict[str, Any]:
    """Convert a domain Farmer to proto format.

    Args:
        farmer: Domain Farmer instance

    Returns:
        Dict representation matching proto AgentState
    """
    # Map domain status to proto enum values
    status_map = {
        AgentStatus.IDLE: 1,
        AgentStatus.THINKING: 2,
        AgentStatus.ACTING: 3,
        AgentStatus.DEAD: 4,
    }

    # Map domain crop types to proto enum values
    crop_type_map = {
        CropType.RICE: 1,
        CropType.CORN: 2,
        CropType.CASSAVA: 3,
        CropType.SOYBEAN: 4,
        CropType.PEANUT: 5,
        CropType.VEGETABLE: 6,
        CropType.FRUIT: 7,
    }

    inventory_items = {
        crop_type_map[crop]: qty
        for crop, qty in farmer.inventory.items()
        if crop in crop_type_map
    }

    return {
        "id": str(farmer.id),
        "name": farmer.name,
        "region_id": str(farmer.region_id),
        "status": status_map.get(farmer.status, 1),
        "cash": farmer.cash,
        "inventory": {"items": inventory_items},
        "land_size": farmer.land_size,
        "health": farmer.health,
        "hunger": farmer.hunger,
        "location": {
            "latitude": farmer.latitude,
            "longitude": farmer.longitude,
        },
    }


def market_to_proto(market: Market) -> dict[str, Any]:
    """Convert a domain Market to proto format.

    Args:
        market: Domain Market instance

    Returns:
        Dict representation matching proto MarketState
    """
    from src.domain.schemas import MarketType

    market_type_map = {
        MarketType.LOCAL: 1,
        MarketType.DISTRICT: 2,
        MarketType.REGIONAL: 3,
    }

    crop_type_map = {
        CropType.RICE: 1,
        CropType.CORN: 2,
        CropType.CASSAVA: 3,
        CropType.SOYBEAN: 4,
        CropType.PEANUT: 5,
        CropType.VEGETABLE: 6,
        CropType.FRUIT: 7,
    }

    prices = {
        crop_type_map[crop]: price
        for crop, price in market.prices.items()
        if crop in crop_type_map
    }

    return {
        "id": str(market.id),
        "name": market.name,
        "region_id": str(market.region_id),
        "market_type": market_type_map.get(market.market_type, 1),
        "location": {
            "latitude": market.latitude,
            "longitude": market.longitude,
        },
        "prices": {"prices": prices},
        "daily_volume": market.daily_volume,
    }


# =============================================================================
# Server Factory
# =============================================================================


async def create_grpc_server(
    host: str = "0.0.0.0",
    port: int = 50051,
    max_workers: int = 10,
) -> tuple[grpc.aio.Server, InferenceServicer]:
    """Create and configure the gRPC server.

    Args:
        host: Server host address
        port: Server port
        max_workers: Maximum worker threads

    Returns:
        Tuple of (server, servicer)
    """
    settings = get_settings()

    # Initialize dependencies
    neo4j_client = await create_neo4j_client()
    llm_router = create_llm_router()

    # Create AgenticRAG
    agentic_rag = AgenticRAG(
        neo4j_client=neo4j_client,
        llm_router=llm_router,
    )

    # Create servicer
    servicer = InferenceServicer(agentic_rag)

    # Create server
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
    )

    # In production with generated stubs:
    # simulation_pb2_grpc.add_InferenceServiceServicer_to_server(servicer, server)

    server.add_insecure_port(f"{host}:{port}")

    logger.info(
        "grpc_server_created",
        host=host,
        port=port,
        max_workers=max_workers,
    )

    return server, servicer


async def run_grpc_server() -> None:
    """Run the gRPC server (blocking)."""
    settings = get_settings()
    host = settings.host
    port = settings.grpc_port

    server, servicer = await create_grpc_server(host=host, port=port)

    await server.start()
    logger.info("grpc_server_started", host=host, port=port)

    try:
        await server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("grpc_server_stopping")
        await server.stop(grace=5)
        logger.info("grpc_server_stopped")


# =============================================================================
# CLI Entry Point
# =============================================================================


if __name__ == "__main__":
    import sys

    from src.logging import configure_logging

    configure_logging()
    asyncio.run(run_grpc_server())
