"""Integration tests for the AI Engine.

These tests verify the end-to-end flow:
1. Go sends agent state to Python via gRPC
2. Python queries Neo4j for context
3. Python calls Cloud LLM for decision
4. Python returns ActionDecision to Go

The tests use mock implementations where external services aren't available.
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.config import get_locale, get_settings
from src.domain.schemas import (
    ActionDecision,
    ActionType,
    AgentContext,
    AgentStatus,
    CropType,
    Farmer,
    Market,
    MarketType,
    Region,
)


# =============================================================================
# Mock Implementations
# =============================================================================


class MockNeo4jClient:
    """Mock Neo4j client for testing without database."""

    def __init__(self) -> None:
        self.farmers: dict[UUID, Farmer] = {}
        self.markets: dict[UUID, Market] = {}
        self.regions: dict[UUID, Region] = {}
        self._setup_test_data()

    def _setup_test_data(self) -> None:
        """Set up test data."""
        # Create a test region
        region_id = uuid4()
        region = Region(
            id=region_id,
            name="Test District",
            code="TEST-001",
            level=3,
            center_latitude=-6.9,
            center_longitude=110.4,
            population=50000,
            area_km2=100.0,
        )
        self.regions[region_id] = region

        # Create test markets
        for i in range(3):
            market_id = uuid4()
            market = Market(
                id=market_id,
                name=f"Test Market {i+1}",
                market_type=MarketType.LOCAL,
                region_id=region_id,
                latitude=-6.9 + (i * 0.01),
                longitude=110.4 + (i * 0.01),
                prices={
                    CropType.RICE: 12000 + (i * 500),
                    CropType.CORN: 5000 + (i * 200),
                },
                daily_volume=1000.0,
            )
            self.markets[market_id] = market

        # Create test farmers
        for i in range(5):
            farmer_id = uuid4()
            farmer = Farmer(
                id=farmer_id,
                name=f"Farmer {i+1}",
                region_id=region_id,
                status=AgentStatus.IDLE,
                cash=500000.0 - (i * 50000),
                inventory={
                    CropType.RICE: 100.0 - (i * 10),
                    CropType.CORN: 50.0,
                },
                land_size=1.0 + (i * 0.5),
                health=100.0 - (i * 5),
                hunger=i * 10.0,
                latitude=-6.9 + (i * 0.005),
                longitude=110.4 + (i * 0.005),
            )
            self.farmers[farmer_id] = farmer

    async def get_farmer(self, farmer_id: UUID) -> Farmer | None:
        return self.farmers.get(farmer_id)

    async def get_farmers_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[Farmer]:
        # Return all farmers for simplicity
        return list(self.farmers.values())

    async def get_market(self, market_id: UUID) -> Market | None:
        return self.markets.get(market_id)

    async def get_markets_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_km: float,
    ) -> list[Market]:
        return list(self.markets.values())

    async def get_region(self, region_id: UUID) -> Region | None:
        return self.regions.get(region_id)

    async def get_trade_relationships(self, agent_id: UUID) -> list:
        return []

    async def detect_communities(self) -> list:
        return []

    async def get_snapshot(self):
        from src.domain.schemas import GraphSnapshot

        return GraphSnapshot(
            farmers=list(self.farmers.values()),
            markets=list(self.markets.values()),
            regions=list(self.regions.values()),
        )

    async def close(self) -> None:
        pass


class MockLLMRouter:
    """Mock LLM router for testing without API calls."""

    def __init__(self) -> None:
        self._decisions: dict[UUID, ActionDecision] = {}
        self._request_count = 0

    def set_decision(self, agent_id: UUID, decision: ActionDecision) -> None:
        """Set a mock decision for an agent."""
        self._decisions[agent_id] = decision

    async def get_client(self):
        return self

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        self._request_count += 1
        return "Mock response"

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type,
        system_prompt: str | None = None,
    ) -> dict:
        self._request_count += 1
        # Return a mock decision
        return {
            "action_type": "idle",
            "target_id": None,
            "parameters": {},
            "reasoning": "Mock decision for testing",
            "confidence": 0.8,
        }

    async def close(self) -> None:
        pass

    def get_stats(self) -> dict[str, Any]:
        return {
            "provider": "mock",
            "model": "mock-model",
            "total_requests": self._request_count,
        }


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_neo4j() -> MockNeo4jClient:
    """Create a mock Neo4j client."""
    return MockNeo4jClient()


@pytest.fixture
def mock_llm() -> MockLLMRouter:
    """Create a mock LLM router."""
    return MockLLMRouter()


@pytest.fixture
def test_farmer(mock_neo4j: MockNeo4jClient) -> Farmer:
    """Get a test farmer."""
    return list(mock_neo4j.farmers.values())[0]


@pytest.fixture
def test_market(mock_neo4j: MockNeo4jClient) -> Market:
    """Get a test market."""
    return list(mock_neo4j.markets.values())[0]


# =============================================================================
# Unit Tests
# =============================================================================


class TestDomainSchemas:
    """Test domain schema validation."""

    def test_farmer_creation(self) -> None:
        """Test Farmer model creation."""
        farmer = Farmer(
            name="Test Farmer",
            region_id=uuid4(),
            latitude=-6.9,
            longitude=110.4,
        )
        assert farmer.name == "Test Farmer"
        assert farmer.status == AgentStatus.IDLE
        assert farmer.cash == 0.0
        assert farmer.health == 100.0
        assert farmer.hunger == 0.0

    def test_market_creation(self) -> None:
        """Test Market model creation."""
        market = Market(
            name="Test Market",
            region_id=uuid4(),
            latitude=-6.9,
            longitude=110.4,
        )
        assert market.name == "Test Market"
        assert market.market_type == MarketType.LOCAL
        assert market.prices == {}

    def test_action_decision_creation(self) -> None:
        """Test ActionDecision model creation."""
        decision = ActionDecision(
            agent_id=uuid4(),
            action_type=ActionType.SELL,
            parameters={"crop_type": "rice", "quantity": 50},
            reasoning="Selling rice at good price",
            confidence=0.85,
        )
        assert decision.action_type == ActionType.SELL
        assert decision.confidence == 0.85


class TestGraphPruning:
    """Test graph pruning and context building."""

    @pytest.mark.asyncio
    async def test_build_agent_context(
        self,
        mock_neo4j: MockNeo4jClient,
        test_farmer: Farmer,
    ) -> None:
        """Test building agent context."""
        from src.usecases.graph_pruning import GraphPruner

        pruner = GraphPruner(mock_neo4j)

        context = await pruner.build_agent_context(
            agent=test_farmer,
            current_tick=100,
        )

        assert context.agent_id == test_farmer.id
        assert context.current_tick == 100
        assert len(context.nearby_markets) > 0
        assert len(context.nearby_farmers) >= 0

    @pytest.mark.asyncio
    async def test_generate_context_summary(
        self,
        mock_neo4j: MockNeo4jClient,
        test_farmer: Farmer,
    ) -> None:
        """Test generating context summary."""
        from src.usecases.graph_pruning import GraphPruner

        pruner = GraphPruner(mock_neo4j)

        context = await pruner.build_agent_context(
            agent=test_farmer,
            current_tick=100,
        )

        summary = await pruner.generate_context_summary(context)

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert test_farmer.name in summary


class TestAgenticRAG:
    """Test the AgenticRAG decision system."""

    @pytest.mark.asyncio
    async def test_single_decision(
        self,
        mock_neo4j: MockNeo4jClient,
        mock_llm: MockLLMRouter,
        test_farmer: Farmer,
    ) -> None:
        """Test generating a single agent decision."""
        from src.usecases.agentic_rag import AgenticRAG

        rag = AgenticRAG(
            neo4j_client=mock_neo4j,
            llm_router=mock_llm,
        )

        decision = await rag.decide(
            agent=test_farmer,
            current_tick=100,
        )

        assert isinstance(decision, ActionDecision)
        assert decision.agent_id == test_farmer.id
        assert decision.action_type in ActionType
        assert 0.0 <= decision.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_batch_decisions(
        self,
        mock_neo4j: MockNeo4jClient,
        mock_llm: MockLLMRouter,
    ) -> None:
        """Test generating batch decisions."""
        from src.usecases.agentic_rag import AgenticRAG

        rag = AgenticRAG(
            neo4j_client=mock_neo4j,
            llm_router=mock_llm,
        )

        agents = list(mock_neo4j.farmers.values())[:3]

        decisions = await rag.decide_batch(
            agents=agents,
            current_tick=100,
        )

        assert len(decisions) == len(agents)
        for agent in agents:
            assert agent.id in decisions
            assert isinstance(decisions[agent.id], ActionDecision)

    @pytest.mark.asyncio
    async def test_fallback_decision_hungry(
        self,
        mock_neo4j: MockNeo4jClient,
        mock_llm: MockLLMRouter,
    ) -> None:
        """Test fallback decision for hungry agent."""
        from src.usecases.agentic_rag import AgenticRAG

        rag = AgenticRAG(
            neo4j_client=mock_neo4j,
            llm_router=mock_llm,
        )

        # Create a very hungry agent
        hungry_farmer = Farmer(
            name="Hungry Farmer",
            region_id=uuid4(),
            latitude=-6.9,
            longitude=110.4,
            hunger=85.0,  # Very hungry
            health=50.0,
        )

        decision = rag._fallback_decision(hungry_farmer)

        assert decision.action_type == ActionType.EAT
        assert "hunger" in decision.reasoning.lower()

    @pytest.mark.asyncio
    async def test_fallback_decision_low_health(
        self,
        mock_neo4j: MockNeo4jClient,
        mock_llm: MockLLMRouter,
    ) -> None:
        """Test fallback decision for low health agent."""
        from src.usecases.agentic_rag import AgenticRAG

        rag = AgenticRAG(
            neo4j_client=mock_neo4j,
            llm_router=mock_llm,
        )

        # Create a low health agent
        sick_farmer = Farmer(
            name="Sick Farmer",
            region_id=uuid4(),
            latitude=-6.9,
            longitude=110.4,
            hunger=20.0,  # Not hungry
            health=20.0,  # Very low health
        )

        decision = rag._fallback_decision(sick_farmer)

        assert decision.action_type == ActionType.REST
        assert "health" in decision.reasoning.lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for the full system."""

    @pytest.mark.asyncio
    async def test_10_tick_simulation(
        self,
        mock_neo4j: MockNeo4jClient,
        mock_llm: MockLLMRouter,
    ) -> None:
        """Run a 10-tick simulation headless.

        This test verifies the core Tick-to-Think loop:
        1. Get agents needing decisions
        2. Build context for each agent
        3. Generate decisions via LLM
        4. Apply decisions (mocked)
        5. Repeat for 10 ticks
        """
        from src.usecases.agentic_rag import AgenticRAG

        rag = AgenticRAG(
            neo4j_client=mock_neo4j,
            llm_router=mock_llm,
        )

        # Track simulation state
        tick_results: list[dict] = []
        total_decisions = 0

        # Run 10 ticks
        for tick in range(1, 11):
            # Get all active agents
            agents = [
                f for f in mock_neo4j.farmers.values()
                if f.status != AgentStatus.DEAD
            ]

            # Generate decisions for all agents
            decisions = await rag.decide_batch(
                agents=agents,
                current_tick=tick,
            )

            # Record results
            tick_result = {
                "tick": tick,
                "agents_processed": len(agents),
                "decisions_made": len(decisions),
                "action_types": [d.action_type.value for d in decisions.values()],
            }
            tick_results.append(tick_result)
            total_decisions += len(decisions)

            # Simulate state changes (hunger increases, etc.)
            for farmer in agents:
                farmer.hunger = min(100.0, farmer.hunger + 2.0)
                if farmer.hunger > 80 and farmer.health > 0:
                    farmer.health = max(0.0, farmer.health - 1.0)

        # Verify simulation completed
        assert len(tick_results) == 10
        assert total_decisions > 0

        # Verify each tick processed agents
        for result in tick_results:
            assert result["agents_processed"] > 0
            assert result["decisions_made"] > 0

        # Log summary
        print(f"\n10-Tick Simulation Complete:")
        print(f"  Total ticks: {len(tick_results)}")
        print(f"  Total decisions: {total_decisions}")
        print(f"  Avg decisions/tick: {total_decisions / 10:.1f}")

    @pytest.mark.asyncio
    async def test_grpc_servicer(
        self,
        mock_neo4j: MockNeo4jClient,
        mock_llm: MockLLMRouter,
    ) -> None:
        """Test the gRPC servicer mock interface."""
        from src.api.grpc_servicer import InferenceServicer, proto_to_farmer, decision_to_proto
        from src.usecases.agentic_rag import AgenticRAG

        rag = AgenticRAG(
            neo4j_client=mock_neo4j,
            llm_router=mock_llm,
        )

        servicer = InferenceServicer(rag)

        # Test that servicer can be created
        assert servicer is not None
        assert servicer.get_stats()["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_agent_tools(
        self,
        mock_neo4j: MockNeo4jClient,
    ) -> None:
        """Test the agent tools for LLM function calling."""
        from src.usecases.agent_tools import AgentTools

        tools = AgentTools(mock_neo4j)

        # Test get_local_price
        result = await tools.get_local_price(
            crop_type="rice",
            latitude=-6.9,
            longitude=110.4,
        )
        assert result.success
        assert result.data["crop_type"] == "rice"

        # Test find_best_market
        result = await tools.find_best_market(
            crop_type="rice",
            latitude=-6.9,
            longitude=110.4,
        )
        assert result.success
        assert result.data.get("best_market") is not None

        # Test check_inventory
        farmer = list(mock_neo4j.farmers.values())[0]
        result = await tools.check_inventory(str(farmer.id))
        assert result.success
        assert "items" in result.data

        # Test get_agent_status
        result = await tools.get_agent_status(str(farmer.id))
        assert result.success
        assert "health" in result.data
        assert "hunger" in result.data


class TestLocalization:
    """Test localization features."""

    def test_locale_config(self) -> None:
        """Test locale configuration."""
        locale = get_locale()
        assert locale.country_code is not None
        assert locale.currency_code is not None
        assert locale.currency_symbol is not None

    def test_currency_formatting(self) -> None:
        """Test currency formatting for different locales."""
        from src.config import LocaleConfig, LOCALE_PRESETS

        # Test Indonesian locale
        id_locale = LocaleConfig(**LOCALE_PRESETS["ID"])
        formatted = id_locale.format_currency(12000)
        assert "Rp" in formatted
        assert "12,000" in formatted or "12000" in formatted

        # Test US locale
        us_locale = LocaleConfig(**LOCALE_PRESETS["US"])
        formatted = us_locale.format_currency(1.50)
        assert "$" in formatted

    def test_admin_level_names(self) -> None:
        """Test administrative level names."""
        from src.config import LocaleConfig, LOCALE_PRESETS

        # Test Indonesian locale
        id_locale = LocaleConfig(**LOCALE_PRESETS["ID"])
        assert id_locale.get_admin_level_name(1) == "Provinsi"
        assert id_locale.get_admin_level_name(3) == "Kecamatan"

        # Test US locale
        us_locale = LocaleConfig(**LOCALE_PRESETS["US"])
        assert us_locale.get_admin_level_name(1) == "State"
        assert us_locale.get_admin_level_name(2) == "County"
