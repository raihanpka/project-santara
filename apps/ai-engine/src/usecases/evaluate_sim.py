"""Simulation evaluation using LLM-as-a-Judge pattern.

This module implements the post-mortem evaluation system that uses
the Cloud LLM to analyze simulation logs and generate a comprehensive
evaluation report.

The LLM-as-a-Judge approach:
1. Collects simulation logs and metrics
2. Sends the data to the Cloud LLM
3. LLM analyzes agent performance, market dynamics, emergent behaviors
4. Returns a structured evaluation report

This is part of Phase 4 but the foundation is implemented here.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.config import get_locale, LocaleConfig
from src.domain.schemas import (
    ActionDecision,
    ActionType,
    AgentStatus,
    CropType,
    Farmer,
    Market,
)
from src.infrastructure.cloud_llm_client import LLMRouter
from src.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Evaluation Models
# =============================================================================


class EvaluationCategory(str, Enum):
    """Categories for simulation evaluation."""

    ECONOMIC_PERFORMANCE = "economic_performance"
    AGENT_BEHAVIOR = "agent_behavior"
    MARKET_DYNAMICS = "market_dynamics"
    EMERGENT_PATTERNS = "emergent_patterns"
    SURVIVAL_RATE = "survival_rate"


class EvaluationScore(BaseModel):
    """Score for a specific evaluation category."""

    category: EvaluationCategory
    score: float = Field(ge=0.0, le=10.0, description="Score out of 10")
    reasoning: str = Field(max_length=500)
    key_observations: list[str] = Field(default_factory=list)


class AgentEvaluation(BaseModel):
    """Evaluation of a single agent's performance."""

    agent_id: str
    agent_name: str
    final_status: AgentStatus
    economic_score: float = Field(ge=0.0, le=10.0)
    survival_score: float = Field(ge=0.0, le=10.0)
    decision_quality: float = Field(ge=0.0, le=10.0)
    highlights: list[str] = Field(default_factory=list)
    areas_for_improvement: list[str] = Field(default_factory=list)


class SimulationEvaluation(BaseModel):
    """Complete simulation evaluation report."""

    simulation_id: str
    start_tick: int
    end_tick: int
    total_ticks: int
    evaluation_timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Overall scores
    overall_score: float = Field(ge=0.0, le=10.0)
    category_scores: list[EvaluationScore] = Field(default_factory=list)

    # Agent evaluations
    agent_evaluations: list[AgentEvaluation] = Field(default_factory=list)

    # Summary
    executive_summary: str = Field(max_length=1000)
    key_insights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    # Statistics
    statistics: dict[str, Any] = Field(default_factory=dict)


@dataclass
class SimulationLog:
    """Container for simulation log data."""

    tick: int
    timestamp: datetime
    agent_states: list[dict[str, Any]]
    market_states: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    events: list[dict[str, Any]]


# =============================================================================
# Simulation Evaluator
# =============================================================================


class SimulationEvaluator:
    """Evaluates simulation runs using LLM-as-a-Judge pattern.

    This class:
    1. Collects and processes simulation logs
    2. Builds evaluation prompts for the LLM
    3. Parses LLM responses into structured evaluations
    4. Generates comprehensive post-mortem reports
    """

    def __init__(
        self,
        llm_router: LLMRouter,
        locale: LocaleConfig | None = None,
    ) -> None:
        """Initialize the evaluator.

        Args:
            llm_router: LLM router for evaluation requests
            locale: Optional locale configuration
        """
        self._llm = llm_router
        self._locale = locale or get_locale()

    async def evaluate_simulation(
        self,
        simulation_id: str,
        logs: list[SimulationLog],
        final_agents: list[Farmer],
        final_markets: list[Market],
    ) -> SimulationEvaluation:
        """Evaluate a completed simulation.

        Args:
            simulation_id: Unique identifier for the simulation
            logs: List of simulation logs
            final_agents: Final state of all agents
            final_markets: Final state of all markets

        Returns:
            Comprehensive SimulationEvaluation
        """
        logger.info(
            "evaluation_start",
            simulation_id=simulation_id,
            log_count=len(logs),
            agent_count=len(final_agents),
        )

        # Calculate statistics
        statistics = self._calculate_statistics(logs, final_agents, final_markets)

        # Build evaluation prompt
        prompt = self._build_evaluation_prompt(
            logs=logs,
            final_agents=final_agents,
            final_markets=final_markets,
            statistics=statistics,
        )

        # Get LLM evaluation
        system_prompt = self._build_system_prompt()

        try:
            response = await self._llm.generate_structured(
                prompt=prompt,
                response_schema=dict,  # Will parse manually
                system_prompt=system_prompt,
            )

            # Parse response into evaluation
            evaluation = self._parse_evaluation_response(
                response=response,
                simulation_id=simulation_id,
                logs=logs,
                final_agents=final_agents,
                statistics=statistics,
            )

        except Exception as e:
            logger.error("evaluation_llm_error", error=str(e))
            # Return a basic evaluation on error
            evaluation = self._create_fallback_evaluation(
                simulation_id=simulation_id,
                logs=logs,
                final_agents=final_agents,
                statistics=statistics,
            )

        logger.info(
            "evaluation_complete",
            simulation_id=simulation_id,
            overall_score=evaluation.overall_score,
        )

        return evaluation

    def _calculate_statistics(
        self,
        logs: list[SimulationLog],
        final_agents: list[Farmer],
        final_markets: list[Market],
    ) -> dict[str, Any]:
        """Calculate simulation statistics."""
        # Agent statistics
        alive_agents = [a for a in final_agents if a.status != AgentStatus.DEAD]
        dead_agents = [a for a in final_agents if a.status == AgentStatus.DEAD]

        total_cash = sum(a.cash for a in alive_agents)
        total_inventory = sum(
            sum(a.inventory.values())
            for a in alive_agents
        )

        avg_health = (
            sum(a.health for a in alive_agents) / len(alive_agents)
            if alive_agents else 0
        )
        avg_cash = total_cash / len(alive_agents) if alive_agents else 0

        # Decision statistics
        all_decisions = []
        for log in logs:
            all_decisions.extend(log.decisions)

        action_counts: dict[str, int] = {}
        for decision in all_decisions:
            action_type = decision.get("action_type", "unknown")
            action_counts[action_type] = action_counts.get(action_type, 0) + 1

        # Market statistics
        avg_prices: dict[str, float] = {}
        for market in final_markets:
            for crop, price in market.prices.items():
                crop_name = crop.value if isinstance(crop, CropType) else str(crop)
                if crop_name not in avg_prices:
                    avg_prices[crop_name] = 0
                avg_prices[crop_name] += price / len(final_markets)

        return {
            "total_ticks": len(logs),
            "total_agents": len(final_agents),
            "alive_agents": len(alive_agents),
            "dead_agents": len(dead_agents),
            "survival_rate": len(alive_agents) / len(final_agents) if final_agents else 0,
            "total_cash": total_cash,
            "average_cash": avg_cash,
            "average_health": avg_health,
            "total_inventory_kg": total_inventory,
            "total_decisions": len(all_decisions),
            "action_distribution": action_counts,
            "average_prices": avg_prices,
            "total_markets": len(final_markets),
        }

    def _build_system_prompt(self) -> str:
        """Build the system prompt for evaluation."""
        return f"""You are an expert simulation analyst evaluating an agrarian micro-economy simulation.

Your task is to provide a comprehensive evaluation of the simulation results, analyzing:
1. Economic Performance: How well did agents manage their finances and resources?
2. Agent Behavior: Were agent decisions rational and effective?
3. Market Dynamics: How did markets respond to supply and demand?
4. Emergent Patterns: What interesting behaviors emerged from the simulation?
5. Survival Rates: How well did agents survive and thrive?

Currency: {self._locale.currency_code} ({self._locale.currency_symbol})
Country Context: {self._locale.country_name}

Provide your evaluation as a JSON object with the following structure:
{{
    "overall_score": <0-10>,
    "executive_summary": "<1-2 paragraph summary>",
    "category_scores": [
        {{
            "category": "<category_name>",
            "score": <0-10>,
            "reasoning": "<explanation>",
            "key_observations": ["<observation1>", "<observation2>"]
        }}
    ],
    "key_insights": ["<insight1>", "<insight2>"],
    "recommendations": ["<recommendation1>", "<recommendation2>"]
}}

Be specific, data-driven, and constructive in your analysis."""

    def _build_evaluation_prompt(
        self,
        logs: list[SimulationLog],
        final_agents: list[Farmer],
        final_markets: list[Market],
        statistics: dict[str, Any],
    ) -> str:
        """Build the evaluation prompt with simulation data."""
        # Format agent summaries
        agent_summaries = []
        for agent in final_agents:
            inventory_str = ", ".join(
                f"{crop.value}: {qty:.1f}kg"
                for crop, qty in agent.inventory.items()
                if qty > 0
            ) or "empty"

            agent_summaries.append(
                f"- {agent.name}: Status={agent.status.value}, "
                f"Cash={self._locale.format_currency(agent.cash)}, "
                f"Health={agent.health:.1f}%, Hunger={agent.hunger:.1f}%, "
                f"Inventory=[{inventory_str}]"
            )

        # Format market summaries
        market_summaries = []
        for market in final_markets:
            prices_str = ", ".join(
                f"{crop.value}: {self._locale.format_currency(price)}"
                for crop, price in market.prices.items()
            )
            market_summaries.append(
                f"- {market.name} ({market.market_type.value}): [{prices_str}]"
            )

        # Format action distribution
        action_dist_str = ", ".join(
            f"{action}: {count}"
            for action, count in statistics.get("action_distribution", {}).items()
        )

        prompt = f"""
SIMULATION EVALUATION REQUEST
=============================

SIMULATION STATISTICS:
- Total Ticks: {statistics.get('total_ticks', 0)}
- Total Agents: {statistics.get('total_agents', 0)}
- Alive Agents: {statistics.get('alive_agents', 0)}
- Dead Agents: {statistics.get('dead_agents', 0)}
- Survival Rate: {statistics.get('survival_rate', 0) * 100:.1f}%
- Total Cash in Economy: {self._locale.format_currency(statistics.get('total_cash', 0))}
- Average Cash per Agent: {self._locale.format_currency(statistics.get('average_cash', 0))}
- Average Health: {statistics.get('average_health', 0):.1f}%
- Total Inventory: {statistics.get('total_inventory_kg', 0):.1f} kg
- Total Decisions Made: {statistics.get('total_decisions', 0)}

ACTION DISTRIBUTION:
{action_dist_str}

FINAL AGENT STATES:
{chr(10).join(agent_summaries[:10])}
{'... and ' + str(len(agent_summaries) - 10) + ' more agents' if len(agent_summaries) > 10 else ''}

MARKET STATES:
{chr(10).join(market_summaries[:5])}
{'... and ' + str(len(market_summaries) - 5) + ' more markets' if len(market_summaries) > 5 else ''}

Please provide a comprehensive evaluation of this simulation.
"""
        return prompt

    def _parse_evaluation_response(
        self,
        response: dict[str, Any],
        simulation_id: str,
        logs: list[SimulationLog],
        final_agents: list[Farmer],
        statistics: dict[str, Any],
    ) -> SimulationEvaluation:
        """Parse LLM response into SimulationEvaluation."""
        # Parse category scores
        category_scores = []
        for score_data in response.get("category_scores", []):
            try:
                category = EvaluationCategory(score_data.get("category", "").lower().replace(" ", "_"))
            except ValueError:
                continue

            category_scores.append(EvaluationScore(
                category=category,
                score=float(score_data.get("score", 5.0)),
                reasoning=score_data.get("reasoning", "")[:500],
                key_observations=score_data.get("key_observations", [])[:5],
            ))

        # Create agent evaluations (simplified)
        agent_evaluations = []
        for agent in final_agents[:10]:  # Limit to first 10
            agent_evaluations.append(AgentEvaluation(
                agent_id=str(agent.id),
                agent_name=agent.name,
                final_status=agent.status,
                economic_score=min(10.0, agent.cash / 100000),  # Simplified scoring
                survival_score=10.0 if agent.status != AgentStatus.DEAD else 0.0,
                decision_quality=7.0,  # Default
                highlights=[],
                areas_for_improvement=[],
            ))

        return SimulationEvaluation(
            simulation_id=simulation_id,
            start_tick=1,
            end_tick=len(logs),
            total_ticks=len(logs),
            overall_score=float(response.get("overall_score", 5.0)),
            category_scores=category_scores,
            agent_evaluations=agent_evaluations,
            executive_summary=response.get("executive_summary", "")[:1000],
            key_insights=response.get("key_insights", [])[:10],
            recommendations=response.get("recommendations", [])[:10],
            statistics=statistics,
        )

    def _create_fallback_evaluation(
        self,
        simulation_id: str,
        logs: list[SimulationLog],
        final_agents: list[Farmer],
        statistics: dict[str, Any],
    ) -> SimulationEvaluation:
        """Create a basic evaluation when LLM fails."""
        survival_rate = statistics.get("survival_rate", 0)
        avg_health = statistics.get("average_health", 0)

        # Simple scoring based on statistics
        overall_score = (survival_rate * 5) + (avg_health / 20)

        return SimulationEvaluation(
            simulation_id=simulation_id,
            start_tick=1,
            end_tick=len(logs),
            total_ticks=len(logs),
            overall_score=min(10.0, max(0.0, overall_score)),
            category_scores=[
                EvaluationScore(
                    category=EvaluationCategory.SURVIVAL_RATE,
                    score=survival_rate * 10,
                    reasoning="Based on agent survival rate",
                    key_observations=[
                        f"{statistics.get('alive_agents', 0)} agents survived",
                        f"{statistics.get('dead_agents', 0)} agents died",
                    ],
                ),
            ],
            agent_evaluations=[],
            executive_summary=(
                f"Simulation completed with {len(logs)} ticks. "
                f"Survival rate: {survival_rate * 100:.1f}%. "
                f"Average health: {avg_health:.1f}%."
            ),
            key_insights=[
                f"Processed {statistics.get('total_decisions', 0)} agent decisions",
            ],
            recommendations=[
                "Review agent decision patterns for optimization opportunities",
            ],
            statistics=statistics,
        )

    def format_report(
        self,
        evaluation: SimulationEvaluation,
        format: str = "markdown",
    ) -> str:
        """Format evaluation as a human-readable report.

        Args:
            evaluation: The evaluation to format
            format: Output format ("markdown" or "text")

        Returns:
            Formatted report string
        """
        if format == "markdown":
            return self._format_markdown_report(evaluation)
        else:
            return self._format_text_report(evaluation)

    def _format_markdown_report(self, evaluation: SimulationEvaluation) -> str:
        """Format as markdown report."""
        lines = [
            f"# Simulation Evaluation Report",
            f"",
            f"**Simulation ID:** {evaluation.simulation_id}",
            f"**Ticks:** {evaluation.start_tick} - {evaluation.end_tick} ({evaluation.total_ticks} total)",
            f"**Evaluation Date:** {evaluation.evaluation_timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"## Overall Score: {evaluation.overall_score:.1f}/10",
            f"",
            f"## Executive Summary",
            f"",
            evaluation.executive_summary,
            f"",
            f"## Category Scores",
            f"",
        ]

        for score in evaluation.category_scores:
            lines.append(f"### {score.category.value.replace('_', ' ').title()}: {score.score:.1f}/10")
            lines.append(f"")
            lines.append(score.reasoning)
            if score.key_observations:
                lines.append(f"")
                lines.append("**Key Observations:**")
                for obs in score.key_observations:
                    lines.append(f"- {obs}")
            lines.append(f"")

        if evaluation.key_insights:
            lines.append(f"## Key Insights")
            lines.append(f"")
            for insight in evaluation.key_insights:
                lines.append(f"- {insight}")
            lines.append(f"")

        if evaluation.recommendations:
            lines.append(f"## Recommendations")
            lines.append(f"")
            for rec in evaluation.recommendations:
                lines.append(f"- {rec}")
            lines.append(f"")

        lines.append(f"## Statistics")
        lines.append(f"")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        for key, value in evaluation.statistics.items():
            if isinstance(value, float):
                lines.append(f"| {key.replace('_', ' ').title()} | {value:.2f} |")
            elif isinstance(value, dict):
                lines.append(f"| {key.replace('_', ' ').title()} | (see breakdown) |")
            else:
                lines.append(f"| {key.replace('_', ' ').title()} | {value} |")

        return "\n".join(lines)

    def _format_text_report(self, evaluation: SimulationEvaluation) -> str:
        """Format as plain text report."""
        lines = [
            "=" * 60,
            "SIMULATION EVALUATION REPORT",
            "=" * 60,
            "",
            f"Simulation ID: {evaluation.simulation_id}",
            f"Ticks: {evaluation.start_tick} - {evaluation.end_tick} ({evaluation.total_ticks} total)",
            f"Overall Score: {evaluation.overall_score:.1f}/10",
            "",
            "-" * 60,
            "EXECUTIVE SUMMARY",
            "-" * 60,
            "",
            evaluation.executive_summary,
            "",
        ]

        if evaluation.key_insights:
            lines.append("-" * 60)
            lines.append("KEY INSIGHTS")
            lines.append("-" * 60)
            lines.append("")
            for i, insight in enumerate(evaluation.key_insights, 1):
                lines.append(f"  {i}. {insight}")
            lines.append("")

        return "\n".join(lines)


# =============================================================================
# Factory Functions
# =============================================================================


async def create_evaluator(
    llm_router: LLMRouter | None = None,
) -> SimulationEvaluator:
    """Create a simulation evaluator.

    Args:
        llm_router: Optional LLM router (created if not provided)

    Returns:
        Configured SimulationEvaluator
    """
    from src.infrastructure.cloud_llm_client import create_llm_router

    if llm_router is None:
        llm_router = create_llm_router()

    return SimulationEvaluator(llm_router=llm_router)
