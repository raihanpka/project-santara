"""Tests for domain schemas."""

from uuid import uuid4

import pytest

from src.domain.schemas import (
    ActionDecision,
    ActionType,
    AgentStatus,
    CropType,
    Farmer,
    Market,
    MarketType,
    Region,
)


class TestFarmerSchema:
    """Tests for the Farmer domain entity."""

    def test_farmer_creation(self) -> None:
        """Test creating a valid Farmer."""
        region_id = uuid4()
        farmer = Farmer(
            name="Test Farmer",
            region_id=region_id,
            latitude=-6.2,
            longitude=106.8,
        )

        assert farmer.name == "Test Farmer"
        assert farmer.region_id == region_id
        assert farmer.status == AgentStatus.IDLE
        assert farmer.health == 100.0
        assert farmer.hunger == 0.0
        assert farmer.cash == 0.0
        assert farmer.inventory == {}

    def test_farmer_with_inventory(self) -> None:
        """Test Farmer with inventory."""
        farmer = Farmer(
            name="Rice Farmer",
            region_id=uuid4(),
            latitude=-6.2,
            longitude=106.8,
            inventory={CropType.RICE: 100.0, CropType.CORN: 50.0},
            cash=500000.0,
        )

        assert farmer.inventory[CropType.RICE] == 100.0
        assert farmer.inventory[CropType.CORN] == 50.0
        assert farmer.cash == 500000.0

    def test_farmer_health_bounds(self) -> None:
        """Test health is bounded between 0 and 100."""
        farmer = Farmer(
            name="Healthy Farmer",
            region_id=uuid4(),
            latitude=-6.2,
            longitude=106.8,
            health=100.0,
        )
        assert farmer.health == 100.0

        # Health should be clamped
        with pytest.raises(ValueError):
            Farmer(
                name="Invalid Farmer",
                region_id=uuid4(),
                latitude=-6.2,
                longitude=106.8,
                health=150.0,  # Invalid
            )


class TestMarketSchema:
    """Tests for the Market domain entity."""

    def test_market_creation(self) -> None:
        """Test creating a valid Market."""
        market = Market(
            name="Pasar Induk",
            region_id=uuid4(),
            market_type=MarketType.REGIONAL,
            latitude=-6.2,
            longitude=106.8,
            prices={CropType.RICE: 12000.0},
        )

        assert market.name == "Pasar Induk"
        assert market.market_type == MarketType.REGIONAL
        assert market.prices[CropType.RICE] == 12000.0

    def test_market_default_values(self) -> None:
        """Test Market default values."""
        market = Market(
            name="Local Market",
            region_id=uuid4(),
            latitude=-6.2,
            longitude=106.8,
        )

        assert market.market_type == MarketType.LOCAL
        assert market.daily_volume == 1000.0
        assert market.prices == {}


class TestRegionSchema:
    """Tests for the Region domain entity."""

    def test_region_creation(self) -> None:
        """Test creating a valid Region."""
        region = Region(
            name="Jawa Barat",
            code="32",
            level=1,
            center_latitude=-6.9,
            center_longitude=107.6,
            population=48000000,
            area_km2=35378.0,
        )

        assert region.name == "Jawa Barat"
        assert region.code == "32"
        assert region.level == 1
        assert region.population == 48000000


class TestActionDecision:
    """Tests for ActionDecision schema."""

    def test_action_decision_creation(self) -> None:
        """Test creating an ActionDecision."""
        agent_id = uuid4()
        target_id = uuid4()

        decision = ActionDecision(
            agent_id=agent_id,
            action_type=ActionType.SELL,
            target_id=target_id,
            parameters={"crop_type": "rice", "quantity": 50.0},
            reasoning="Market prices are favorable",
            confidence=0.85,
        )

        assert decision.agent_id == agent_id
        assert decision.action_type == ActionType.SELL
        assert decision.target_id == target_id
        assert decision.confidence == 0.85

    def test_action_decision_idle(self) -> None:
        """Test IDLE action decision."""
        decision = ActionDecision(
            agent_id=uuid4(),
            action_type=ActionType.IDLE,
            reasoning="Nothing to do",
        )

        assert decision.action_type == ActionType.IDLE
        assert decision.target_id is None
        assert decision.parameters == {}
