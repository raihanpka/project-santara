// Package queries contains query handlers for read-only operations.
// This implements the CQRS-Lite pattern from ThreeDotsLabs.
package queries

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog"

	"github.com/santara/sim-engine/internal/domain"
)

// WorldState represents the summary state of the simulation.
type WorldState struct {
	CurrentTick    int64
	TickTimestamp  time.Time

	// Entity counts
	TotalAgents    int
	ActiveAgents   int
	ThinkingAgents int
	DeadAgents     int
	TotalMarkets   int
	TotalRegions   int

	// Statistics
	Statistics WorldStatistics
}

// WorldStatistics holds aggregate statistics.
type WorldStatistics struct {
	TotalCash           float64
	TotalInventoryValue float64
	AverageHealth       float64
	AverageCash         float64
	TotalTrades         int64
	TotalTradeVolume    float64
}

// WorldSnapshot includes all entity states.
type WorldSnapshot struct {
	State   WorldState
	Agents  []*domain.Agent
	Markets []*domain.Market
	Regions []*domain.Region
}

// GetWorldStateQuery represents a query for the current world state.
type GetWorldStateQuery struct {
	IncludeEntities bool // If true, return full snapshot
	CurrentTick     int64
}

// GetWorldStateHandler handles the GetWorldState query.
type GetWorldStateHandler struct {
	agentRepo  domain.AgentRepository
	marketRepo domain.MarketRepository
	regionRepo domain.RegionRepository
	logger     zerolog.Logger
}

// NewGetWorldStateHandler creates a new GetWorldStateHandler.
func NewGetWorldStateHandler(
	agentRepo domain.AgentRepository,
	marketRepo domain.MarketRepository,
	regionRepo domain.RegionRepository,
	logger zerolog.Logger,
) *GetWorldStateHandler {
	return &GetWorldStateHandler{
		agentRepo:  agentRepo,
		marketRepo: marketRepo,
		regionRepo: regionRepo,
		logger:     logger,
	}
}

// Handle executes the GetWorldState query.
func (h *GetWorldStateHandler) Handle(ctx context.Context, query GetWorldStateQuery) (*WorldSnapshot, error) {
	snapshot := &WorldSnapshot{
		State: WorldState{
			CurrentTick:   query.CurrentTick,
			TickTimestamp: time.Now().UTC(),
		},
	}

	// Get all agents
	agents, err := h.agentRepo.GetAll(ctx)
	if err != nil {
		return nil, err
	}

	// Calculate agent statistics
	var (
		activeCount   int
		thinkingCount int
		deadCount     int
		totalCash     float64
		totalHealth   float64
		healthCount   int
	)

	for _, agent := range agents {
		switch agent.Status {
		case domain.AgentStatusDead:
			deadCount++
		case domain.AgentStatusThinking:
			thinkingCount++
			activeCount++
		default:
			activeCount++
		}

		if agent.Status != domain.AgentStatusDead {
			totalCash += agent.Cash
			totalHealth += agent.Health
			healthCount++
		}
	}

	snapshot.State.TotalAgents = len(agents)
	snapshot.State.ActiveAgents = activeCount
	snapshot.State.ThinkingAgents = thinkingCount
	snapshot.State.DeadAgents = deadCount

	// Get markets and regions
	markets, err := h.marketRepo.GetAll(ctx)
	if err != nil {
		return nil, err
	}
	snapshot.State.TotalMarkets = len(markets)

	regions, err := h.regionRepo.GetAll(ctx)
	if err != nil {
		return nil, err
	}
	snapshot.State.TotalRegions = len(regions)

	// Calculate statistics
	snapshot.State.Statistics.TotalCash = totalCash
	if healthCount > 0 {
		snapshot.State.Statistics.AverageHealth = totalHealth / float64(healthCount)
		snapshot.State.Statistics.AverageCash = totalCash / float64(healthCount)
	}

	// Calculate total inventory value
	avgPrices := calculateAveragePrices(markets)
	for _, agent := range agents {
		snapshot.State.Statistics.TotalInventoryValue += agent.GetInventoryValue(avgPrices)
	}

	// Include entities if requested
	if query.IncludeEntities {
		// Clone agents to avoid race conditions
		snapshot.Agents = make([]*domain.Agent, len(agents))
		for i, agent := range agents {
			snapshot.Agents[i] = agent.Clone()
		}

		snapshot.Markets = make([]*domain.Market, len(markets))
		for i, market := range markets {
			snapshot.Markets[i] = market.Clone()
		}

		snapshot.Regions = make([]*domain.Region, len(regions))
		for i, region := range regions {
			snapshot.Regions[i] = region.Clone()
		}
	}

	return snapshot, nil
}

// calculateAveragePrices calculates average prices across all markets.
func calculateAveragePrices(markets []*domain.Market) map[domain.CropType]float64 {
	priceSum := make(map[domain.CropType]float64)
	priceCount := make(map[domain.CropType]int)

	for _, market := range markets {
		for crop, price := range market.Prices {
			priceSum[crop] += price
			priceCount[crop]++
		}
	}

	avgPrices := make(map[domain.CropType]float64)
	for crop, sum := range priceSum {
		if count := priceCount[crop]; count > 0 {
			avgPrices[crop] = sum / float64(count)
		}
	}

	return avgPrices
}

// GetAgentQuery represents a query for a specific agent.
type GetAgentQuery struct {
	AgentID uuid.UUID
}

// GetAgentHandler handles the GetAgent query.
type GetAgentHandler struct {
	agentRepo domain.AgentRepository
	logger    zerolog.Logger
}

// NewGetAgentHandler creates a new GetAgentHandler.
func NewGetAgentHandler(
	agentRepo domain.AgentRepository,
	logger zerolog.Logger,
) *GetAgentHandler {
	return &GetAgentHandler{
		agentRepo: agentRepo,
		logger:    logger,
	}
}

// Handle executes the GetAgent query.
func (h *GetAgentHandler) Handle(ctx context.Context, query GetAgentQuery) (*domain.Agent, error) {
	agent, err := h.agentRepo.Get(ctx, query.AgentID)
	if err != nil {
		return nil, err
	}

	if agent == nil {
		return nil, nil
	}

	return agent.Clone(), nil
}

// GetNearbyMarketsQuery represents a query for markets near a location.
type GetNearbyMarketsQuery struct {
	Location domain.Coordinates
	RadiusKm float64
}

// GetNearbyMarketsHandler handles the GetNearbyMarkets query.
type GetNearbyMarketsHandler struct {
	marketRepo domain.MarketRepository
	logger     zerolog.Logger
}

// NewGetNearbyMarketsHandler creates a new GetNearbyMarketsHandler.
func NewGetNearbyMarketsHandler(
	marketRepo domain.MarketRepository,
	logger zerolog.Logger,
) *GetNearbyMarketsHandler {
	return &GetNearbyMarketsHandler{
		marketRepo: marketRepo,
		logger:     logger,
	}
}

// Handle executes the GetNearbyMarkets query.
func (h *GetNearbyMarketsHandler) Handle(ctx context.Context, query GetNearbyMarketsQuery) ([]*domain.Market, error) {
	markets, err := h.marketRepo.GetNearby(ctx, query.Location, query.RadiusKm)
	if err != nil {
		return nil, err
	}

	// Clone markets for thread safety
	result := make([]*domain.Market, len(markets))
	for i, market := range markets {
		result[i] = market.Clone()
	}

	return result, nil
}
