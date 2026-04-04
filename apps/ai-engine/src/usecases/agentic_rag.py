"""Agentic RAG (Retrieval-Augmented Generation) for agent decision-making.

This module orchestrates the "Think" phase of the Tick-to-Think loop:
1. Receives agent state from Go simulation engine
2. Queries Neo4j for relevant context (RAG)
3. Sends context to Cloud LLM for decision
4. Returns structured action decision to Go engine

This is the core intelligence layer of the Santara simulation.
"""

import json
from typing import Any
from uuid import UUID

from src.config import get_locale, LocaleConfig
from src.domain.repositories import LLMError
from src.domain.schemas import (
    ActionDecision,
    ActionType,
    AgentContext,
    Farmer,
)
from src.infrastructure.cloud_llm_client import LLMRouter
from src.infrastructure.neo4j_client import Neo4jClient
from src.logging import get_logger
from src.usecases.graph_pruning import GraphPruner, PruningConfig

logger = get_logger(__name__)


def build_system_prompt(locale: LocaleConfig) -> str:
    """Build the LLM system prompt based on locale configuration.

    This allows the simulation to be adapted for different countries/regions.
    """
    return f"""You are an AI controlling a farmer agent in an economic simulation of {locale.country_name} agrarian micro-economies.

Your goal is to help the farmer survive and prosper by making smart economic decisions.

The farmer can take these actions:
- IDLE: Do nothing this tick
- MOVE: Travel to a location (specify target coordinates or market ID)
- PLANT: Plant crops (specify crop_type in parameters)
- HARVEST: Harvest ready crops
- SELL: Sell crops at a market (specify market_id and crop_type)
- BUY: Buy supplies from a market
- EAT: Consume food to reduce hunger
- REST: Rest to recover health

Currency: {locale.currency_code} ({locale.currency_symbol})

Guidelines:
1. Prioritize survival: Keep hunger below 70% and health above 30%
2. Economic efficiency: Sell crops when prices are favorable
3. Plan ahead: Consider travel time and market conditions
4. Avoid greed: Don't overextend or take unnecessary risks

Respond with a JSON object containing your decision.
"""


class AgenticRAG:
    """Orchestrates Retrieval-Augmented Generation for agent decisions.

    This class implements the core "Think" logic:
    1. Build context from Neo4j (Retrieval)
    2. Augment with relevant summaries (Augmentation)
    3. Generate decision via LLM (Generation)
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        llm_router: LLMRouter,
        pruning_config: PruningConfig | None = None,
        locale: LocaleConfig | None = None,
    ) -> None:
        """Initialize the Agentic RAG system.

        Args:
            neo4j_client: Connected Neo4j client
            llm_router: Configured LLM router
            pruning_config: Optional pruning configuration
            locale: Optional locale configuration (defaults to global)
        """
        self._neo4j = neo4j_client
        self._llm = llm_router
        self._pruner = GraphPruner(neo4j_client, pruning_config)
        self._locale = locale or get_locale()
        self._decision_cache: dict[UUID, ActionDecision] = {}

    async def decide(
        self,
        agent: Farmer,
        current_tick: int,
        weather: dict[str, Any] | None = None,
    ) -> ActionDecision:
        """Generate a decision for an agent.

        This is the main entry point for the Think phase.

        Args:
            agent: Agent requiring a decision
            current_tick: Current simulation tick
            weather: Optional weather conditions

        Returns:
            ActionDecision for the agent to execute
        """
        logger.info(
            "agentic_rag_decide_start",
            agent_id=str(agent.id),
            tick=current_tick,
        )

        try:
            # Step 1: Build context (Retrieval)
            context = await self._pruner.build_agent_context(
                agent=agent,
                current_tick=current_tick,
                weather=weather,
            )

            # Step 2: Generate summary (Augmentation)
            summary = await self._pruner.generate_context_summary(context)

            # Step 3: Build prompt
            prompt = self._build_decision_prompt(context, summary)

            # Step 4: Generate decision (Generation)
            decision = await self._generate_decision(agent.id, prompt)

            # Cache the decision
            self._decision_cache[agent.id] = decision

            logger.info(
                "agentic_rag_decide_complete",
                agent_id=str(agent.id),
                action=decision.action_type.value,
                confidence=decision.confidence,
            )

            return decision

        except LLMError as e:
            logger.error(
                "agentic_rag_llm_error",
                agent_id=str(agent.id),
                error=str(e),
            )
            # Return a safe fallback action
            return self._fallback_decision(agent)

        except Exception as e:
            logger.error(
                "agentic_rag_error",
                agent_id=str(agent.id),
                error=str(e),
            )
            return self._fallback_decision(agent)

    async def decide_batch(
        self,
        agents: list[Farmer],
        current_tick: int,
        weather: dict[str, Any] | None = None,
    ) -> dict[UUID, ActionDecision]:
        """Generate decisions for multiple agents.

        Optimizes by batching Neo4j queries and LLM calls.

        Args:
            agents: List of agents requiring decisions
            current_tick: Current simulation tick
            weather: Optional weather conditions

        Returns:
            Mapping of agent ID to their decision
        """
        logger.info(
            "agentic_rag_batch_start",
            agent_count=len(agents),
            tick=current_tick,
        )

        # Build contexts in batch
        contexts = await self._pruner.prune_for_batch_reasoning(
            agents=agents,
            current_tick=current_tick,
        )

        # Generate decisions (could be parallelized with asyncio.gather)
        decisions: dict[UUID, ActionDecision] = {}
        for agent in agents:
            context = contexts.get(agent.id)
            if context:
                summary = await self._pruner.generate_context_summary(context)
                prompt = self._build_decision_prompt(context, summary)
                try:
                    decisions[agent.id] = await self._generate_decision(agent.id, prompt)
                except LLMError:
                    decisions[agent.id] = self._fallback_decision(agent)
            else:
                decisions[agent.id] = self._fallback_decision(agent)

        logger.info(
            "agentic_rag_batch_complete",
            agent_count=len(agents),
            decisions_count=len(decisions),
        )

        return decisions

    def _build_decision_prompt(
        self,
        context: AgentContext,
        summary: str,
    ) -> str:
        """Build the prompt for LLM decision generation."""
        agent = context.agent_state

        # Format nearby markets with locale-aware currency
        markets_info = []
        for market in context.nearby_markets:
            prices_str = ", ".join(
                f"{crop.value}: {self._locale.format_currency(price)}"
                for crop, price in market.prices.items()
            )
            markets_info.append(
                f"- {market.name} ({market.market_type.value}): prices=[{prices_str}]"
            )
        markets_section = "\n".join(markets_info) if markets_info else "No markets nearby"

        # Format inventory
        inventory_str = ", ".join(
            f"{crop.value}: {qty:.1f}kg"
            for crop, qty in agent.inventory.items()
            if qty > 0
        ) or "empty"

        prompt = f"""
CURRENT SITUATION:
{summary}

DETAILED STATE:
- Name: {agent.name}
- Location: ({agent.latitude:.4f}, {agent.longitude:.4f})
- Health: {agent.health:.1f}%
- Hunger: {agent.hunger:.1f}%
- Cash: {self._locale.format_currency(agent.cash)}
- Inventory: {inventory_str}
- Land Size: {agent.land_size:.1f} hectares

NEARBY MARKETS:
{markets_section}

NEARBY FARMERS: {len(context.nearby_farmers)} farmers in the area

CURRENT TICK: {context.current_tick}

Based on this situation, decide what action the farmer should take.
Respond with a JSON object containing:
{{
    "action_type": "<one of: idle, move, plant, harvest, sell, buy, eat, rest>",
    "target_id": "<optional UUID of target market/location>",
    "parameters": {{<action-specific parameters>}},
    "reasoning": "<brief explanation of your decision>",
    "confidence": <0.0 to 1.0>
}}

What should this farmer do?
"""
        return prompt

    async def _generate_decision(
        self,
        agent_id: UUID,
        prompt: str,
    ) -> ActionDecision:
        """Generate a decision using the LLM."""
        system_prompt = build_system_prompt(self._locale)

        response = await self._llm.generate_structured(
            prompt=prompt,
            response_schema=ActionDecision,
            system_prompt=system_prompt,
        )

        # Parse the response into ActionDecision
        action_type_str = response.get("action_type", "idle").lower()
        try:
            action_type = ActionType(action_type_str)
        except ValueError:
            action_type = ActionType.IDLE

        target_id = None
        if response.get("target_id"):
            try:
                target_id = UUID(response["target_id"])
            except (ValueError, TypeError):
                pass

        return ActionDecision(
            agent_id=agent_id,
            action_type=action_type,
            target_id=target_id,
            parameters=response.get("parameters", {}),
            reasoning=response.get("reasoning", "")[:500],
            confidence=float(response.get("confidence", 0.5)),
        )

    def _fallback_decision(self, agent: Farmer) -> ActionDecision:
        """Generate a safe fallback decision when LLM fails.

        Prioritizes survival actions based on agent state.
        """
        # Survival priority: eat if hungry, rest if low health
        if agent.hunger > 70:
            action = ActionType.EAT
            reasoning = "Fallback: high hunger, eating to survive"
        elif agent.health < 30:
            action = ActionType.REST
            reasoning = "Fallback: low health, resting to recover"
        else:
            action = ActionType.IDLE
            reasoning = "Fallback: LLM unavailable, waiting"

        return ActionDecision(
            agent_id=agent.id,
            action_type=action,
            parameters={},
            reasoning=reasoning,
            confidence=0.3,  # Low confidence for fallback
        )

    def get_cached_decision(self, agent_id: UUID) -> ActionDecision | None:
        """Get a previously generated decision from cache."""
        return self._decision_cache.get(agent_id)

    def clear_cache(self) -> None:
        """Clear the decision cache."""
        self._decision_cache.clear()

    async def close(self) -> None:
        """Clean up resources."""
        await self._llm.close()


# =============================================================================
# Factory Functions
# =============================================================================


async def create_agentic_rag(
    neo4j_client: Neo4jClient | None = None,
    llm_router: LLMRouter | None = None,
) -> AgenticRAG:
    """Create and initialize an AgenticRAG instance.

    Args:
        neo4j_client: Optional Neo4j client (created if not provided)
        llm_router: Optional LLM router (created if not provided)

    Returns:
        Initialized AgenticRAG instance
    """
    from src.infrastructure.cloud_llm_client import create_llm_router
    from src.infrastructure.neo4j_client import create_neo4j_client

    if neo4j_client is None:
        neo4j_client = await create_neo4j_client()

    if llm_router is None:
        llm_router = create_llm_router()

    return AgenticRAG(
        neo4j_client=neo4j_client,
        llm_router=llm_router,
    )
