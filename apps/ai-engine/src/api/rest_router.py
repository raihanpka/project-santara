"""FastAPI REST router for the Santara AI Engine.

This module provides HTTP endpoints for:
- Health checks and status
- Agent decision requests
- Graph queries
- LLM statistics
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from src.config import get_settings, get_locale, LocaleConfig, LOCALE_PRESETS
from src.domain.schemas import (
    ActionDecision,
    ActionType,
    AgentContext,
    CommunityNode,
    CropType,
    Farmer,
    GraphSnapshot,
    Market,
    Region,
)
from src.infrastructure.cloud_llm_client import LLMRouter, create_llm_router
from src.infrastructure.neo4j_client import Neo4jClient, create_neo4j_client
from src.logging import configure_logging, get_logger
from src.usecases.agentic_rag import AgenticRAG
from src.usecases.graph_pruning import GraphPruner

logger = get_logger(__name__)

# =============================================================================
# Request/Response Models
# =============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0"
    neo4j_connected: bool = False
    llm_provider: str = ""


class DecisionRequest(BaseModel):
    """Request for an agent decision."""

    agent: Farmer = Field(description="Current agent state")
    current_tick: int = Field(ge=0, description="Current simulation tick")
    weather: dict[str, Any] = Field(default_factory=dict, description="Weather conditions")


class DecisionResponse(BaseModel):
    """Response containing agent decision."""

    decision: ActionDecision
    context_summary: str = Field(default="", description="Context used for decision")


class BatchDecisionRequest(BaseModel):
    """Request for batch agent decisions."""

    agents: list[Farmer] = Field(description="List of agents needing decisions")
    current_tick: int = Field(ge=0, description="Current simulation tick")
    weather: dict[str, Any] = Field(default_factory=dict, description="Weather conditions")


class BatchDecisionResponse(BaseModel):
    """Response containing batch decisions."""

    decisions: dict[str, ActionDecision] = Field(description="Agent ID -> Decision mapping")
    total_agents: int
    successful: int


class StatsResponse(BaseModel):
    """Service statistics response."""

    llm_stats: dict[str, Any]
    graph_stats: dict[str, Any]


# =============================================================================
# Application State
# =============================================================================


class AppState:
    """Application state container."""

    neo4j_client: Neo4jClient | None = None
    llm_router: LLMRouter | None = None
    agentic_rag: AgenticRAG | None = None
    graph_pruner: GraphPruner | None = None


app_state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan handler for startup/shutdown."""
    configure_logging()
    logger.info("ai_engine_starting")

    # Initialize Neo4j
    try:
        app_state.neo4j_client = await create_neo4j_client()
        logger.info("neo4j_initialized")
    except Exception as e:
        logger.error("neo4j_init_failed", error=str(e))
        app_state.neo4j_client = None

    # Initialize LLM Router
    app_state.llm_router = create_llm_router()

    # Initialize services
    if app_state.neo4j_client:
        app_state.graph_pruner = GraphPruner(app_state.neo4j_client)
        app_state.agentic_rag = AgenticRAG(
            neo4j_client=app_state.neo4j_client,
            llm_router=app_state.llm_router,
        )

    logger.info("ai_engine_ready")

    yield

    # Shutdown
    logger.info("ai_engine_shutting_down")
    if app_state.llm_router:
        await app_state.llm_router.close()
    if app_state.neo4j_client:
        await app_state.neo4j_client.close()
    logger.info("ai_engine_stopped")


# =============================================================================
# Routers
# =============================================================================

# Health router
health_router = APIRouter(prefix="/health", tags=["Health"])


@health_router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check service health."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        neo4j_connected=app_state.neo4j_client is not None,
        llm_provider=settings.llm_service.value,
    )


@health_router.get("/ready")
async def readiness_check() -> dict[str, bool]:
    """Check if service is ready to handle requests."""
    ready = (
        app_state.neo4j_client is not None
        and app_state.agentic_rag is not None
    )
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready",
        )
    return {"ready": True}


# Decision router
decision_router = APIRouter(prefix="/decide", tags=["Decisions"])


@decision_router.post("", response_model=DecisionResponse)
async def decide(request: DecisionRequest) -> DecisionResponse:
    """Generate a decision for a single agent."""
    if app_state.agentic_rag is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agentic RAG not initialized",
        )

    decision = await app_state.agentic_rag.decide(
        agent=request.agent,
        current_tick=request.current_tick,
        weather=request.weather,
    )

    # Generate context summary
    context_summary = ""
    if app_state.graph_pruner:
        context = await app_state.graph_pruner.build_agent_context(
            agent=request.agent,
            current_tick=request.current_tick,
            weather=request.weather,
        )
        context_summary = await app_state.graph_pruner.generate_context_summary(context)

    return DecisionResponse(
        decision=decision,
        context_summary=context_summary,
    )


@decision_router.post("/batch", response_model=BatchDecisionResponse)
async def decide_batch(request: BatchDecisionRequest) -> BatchDecisionResponse:
    """Generate decisions for multiple agents."""
    if app_state.agentic_rag is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agentic RAG not initialized",
        )

    decisions = await app_state.agentic_rag.decide_batch(
        agents=request.agents,
        current_tick=request.current_tick,
        weather=request.weather,
    )

    # Convert UUID keys to strings for JSON serialization
    decisions_str = {str(k): v for k, v in decisions.items()}

    return BatchDecisionResponse(
        decisions=decisions_str,
        total_agents=len(request.agents),
        successful=len(decisions),
    )


# Graph router
graph_router = APIRouter(prefix="/graph", tags=["Graph"])


@graph_router.get("/snapshot", response_model=GraphSnapshot)
async def get_graph_snapshot() -> GraphSnapshot:
    """Get a full snapshot of the knowledge graph."""
    if app_state.neo4j_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j not connected",
        )
    return await app_state.neo4j_client.get_snapshot()


@graph_router.get("/communities", response_model=list[CommunityNode])
async def get_communities() -> list[CommunityNode]:
    """Get community summaries for graph pruning."""
    if app_state.graph_pruner is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph pruner not initialized",
        )
    return await app_state.graph_pruner.get_community_summaries()


@graph_router.get("/farmers/{farmer_id}", response_model=Farmer)
async def get_farmer(farmer_id: UUID) -> Farmer:
    """Get a farmer by ID."""
    if app_state.neo4j_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j not connected",
        )
    farmer = await app_state.neo4j_client.get_farmer(farmer_id)
    if farmer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Farmer {farmer_id} not found",
        )
    return farmer


@graph_router.get("/markets/nearby")
async def get_nearby_markets(
    latitude: float,
    longitude: float,
    radius_km: float = 50.0,
) -> list[Market]:
    """Get markets within a radius of a location."""
    if app_state.neo4j_client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Neo4j not connected",
        )
    return await app_state.neo4j_client.get_markets_nearby(
        latitude=latitude,
        longitude=longitude,
        radius_km=radius_km,
    )


# Stats router
stats_router = APIRouter(prefix="/stats", tags=["Statistics"])


@stats_router.get("", response_model=StatsResponse)
async def get_stats() -> StatsResponse:
    """Get service statistics."""
    llm_stats = {}
    if app_state.llm_router:
        llm_stats = app_state.llm_router.get_stats()

    graph_stats = {}
    if app_state.neo4j_client:
        snapshot = await app_state.neo4j_client.get_snapshot()
        graph_stats = {
            "farmers_count": len(snapshot.farmers),
            "markets_count": len(snapshot.markets),
            "regions_count": len(snapshot.regions),
            "communities_count": len(snapshot.communities),
        }

    return StatsResponse(
        llm_stats=llm_stats,
        graph_stats=graph_stats,
    )


# Locale/Settings router (for future Web UI configuration)
locale_router = APIRouter(prefix="/locale", tags=["Localization"])


class LocaleResponse(BaseModel):
    """Current locale configuration response."""

    config: LocaleConfig
    available_presets: list[str]


class LocaleUpdateRequest(BaseModel):
    """Request to update locale settings (for future Web UI)."""

    country_code: str | None = None
    currency_code: str | None = None
    currency_symbol: str | None = None
    admin_level_names: dict[int, str] | None = None
    default_crop_prices: dict[str, float] | None = None


@locale_router.get("", response_model=LocaleResponse)
async def get_current_locale() -> LocaleResponse:
    """Get the current locale configuration.

    This endpoint returns the active localization settings including
    currency, administrative level names, and default prices.
    """
    locale = get_locale()
    return LocaleResponse(
        config=locale,
        available_presets=list(LOCALE_PRESETS.keys()),
    )


@locale_router.get("/presets", response_model=dict[str, LocaleConfig])
async def get_locale_presets() -> dict[str, LocaleConfig]:
    """Get all available locale presets.

    Returns preset configurations for different countries.
    """
    return {code: LocaleConfig(**data) for code, data in LOCALE_PRESETS.items()}


@locale_router.get("/presets/{country_code}", response_model=LocaleConfig)
async def get_locale_preset(country_code: str) -> LocaleConfig:
    """Get a specific locale preset by country code."""
    country_code = country_code.upper()
    if country_code not in LOCALE_PRESETS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Locale preset not found for country code: {country_code}",
        )
    return LocaleConfig(**LOCALE_PRESETS[country_code])


@locale_router.post("/preview", response_model=LocaleConfig)
async def preview_locale_changes(request: LocaleUpdateRequest) -> LocaleConfig:
    """Preview locale changes without applying them.

    This endpoint allows the Web UI to show a preview of settings
    before the user saves them.
    """
    # Start with current locale
    current = get_locale()
    preview_data = current.model_dump()

    # Apply requested changes
    if request.country_code:
        # Load preset and merge
        preset_data = LOCALE_PRESETS.get(request.country_code.upper(), {})
        preview_data.update(preset_data)

    if request.currency_code:
        preview_data["currency_code"] = request.currency_code
    if request.currency_symbol:
        preview_data["currency_symbol"] = request.currency_symbol
    if request.admin_level_names:
        preview_data["admin_level_names"].update(request.admin_level_names)
    if request.default_crop_prices:
        preview_data["default_crop_prices"].update(request.default_crop_prices)

    return LocaleConfig(**preview_data)


@locale_router.get("/format-currency")
async def format_currency_example(amount: float = 10000.0) -> dict[str, str]:
    """Format a currency amount using current locale.

    Useful for Web UI to show formatted examples.
    """
    locale = get_locale()
    return {
        "amount": amount,
        "formatted": locale.format_currency(amount),
        "currency_code": locale.currency_code,
        "currency_symbol": locale.currency_symbol,
    }


# =============================================================================
# Application Factory
# =============================================================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Santara AI Engine",
        description="Inference Gateway for multi-agent agrarian simulation",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Include routers
    app.include_router(health_router)
    app.include_router(decision_router)
    app.include_router(graph_router)
    app.include_router(stats_router)
    app.include_router(locale_router)

    return app


# Create default app instance
app = create_app()
