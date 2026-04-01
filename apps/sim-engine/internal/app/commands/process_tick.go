// Package commands contains command handlers for state-mutating operations.
// This implements the CQRS-Lite pattern from ThreeDotsLabs.
package commands

import (
	"context"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog"

	"github.com/santara/sim-engine/internal/domain"
)

// ProcessTickCommand represents the command to advance the simulation by one tick.
type ProcessTickCommand struct {
	TickNumber int64
	HungerRate float64 // Hunger increase per tick
	HealthDecayRate float64 // Health decay when hungry
}

// ProcessTickResult contains the result of processing a tick.
type ProcessTickResult struct {
	TickNumber       int64
	AgentsProcessed  int
	ActionsExecuted  int
	AgentsDied       int
	DecisionsNeeded  int
	DurationMs       int64
}

// ProcessTickHandler handles the ProcessTick command.
type ProcessTickHandler struct {
	agentRepo     domain.AgentRepository
	marketRepo    domain.MarketRepository
	inferenceClient domain.InferenceClient
	logger        zerolog.Logger

	// Configuration
	maxConcurrentThinking int
}

// NewProcessTickHandler creates a new ProcessTickHandler.
func NewProcessTickHandler(
	agentRepo domain.AgentRepository,
	marketRepo domain.MarketRepository,
	inferenceClient domain.InferenceClient,
	logger zerolog.Logger,
	maxConcurrentThinking int,
) *ProcessTickHandler {
	return &ProcessTickHandler{
		agentRepo:            agentRepo,
		marketRepo:           marketRepo,
		inferenceClient:      inferenceClient,
		logger:               logger,
		maxConcurrentThinking: maxConcurrentThinking,
	}
}

// Handle executes the ProcessTick command.
func (h *ProcessTickHandler) Handle(ctx context.Context, cmd ProcessTickCommand) (*ProcessTickResult, error) {
	start := time.Now()
	result := &ProcessTickResult{
		TickNumber: cmd.TickNumber,
	}

	h.logger.Debug().Int64("tick", cmd.TickNumber).Msg("processing tick")

	// 1. Get all alive agents
	agents, err := h.agentRepo.GetAll(ctx)
	if err != nil {
		return nil, err
	}

	// 2. Apply per-tick effects to all agents
	var wg sync.WaitGroup
	var mu sync.Mutex
	var died int

	for _, agent := range agents {
		if agent.Status == domain.AgentStatusDead {
			continue
		}

		wg.Add(1)
		go func(a *domain.Agent) {
			defer wg.Done()

			// Apply tick effects
			a.Tick(cmd.HungerRate, cmd.HealthDecayRate)

			// Check if agent died
			if a.Status == domain.AgentStatusDead {
				mu.Lock()
				died++
				mu.Unlock()
			}

			// Save updated state
			_ = h.agentRepo.Save(ctx, a)
		}(agent)
	}
	wg.Wait()

	result.AgentsDied = died
	result.AgentsProcessed = len(agents) - died

	// 3. Find agents that need decisions
	agentsNeedingDecision := make([]*domain.Agent, 0)
	thinkingCount := 0

	for _, agent := range agents {
		if agent.Status == domain.AgentStatusThinking {
			thinkingCount++
		}
		if agent.NeedsDecision() && thinkingCount < h.maxConcurrentThinking {
			agentsNeedingDecision = append(agentsNeedingDecision, agent)
		}
	}

	result.DecisionsNeeded = len(agentsNeedingDecision)

	// 4. Request decisions from AI Engine (non-blocking for main loop)
	if len(agentsNeedingDecision) > 0 && h.inferenceClient != nil {
		// Mark agents as thinking
		for _, agent := range agentsNeedingDecision {
			if err := agent.SetThinking(); err == nil {
				_ = h.agentRepo.Save(ctx, agent)
			}
		}

		// Request decisions asynchronously
		go h.requestDecisionsAsync(ctx, agentsNeedingDecision, cmd.TickNumber)
	}

	// 5. Update markets (price adjustments)
	markets, err := h.marketRepo.GetAll(ctx)
	if err == nil {
		for _, market := range markets {
			market.UpdatePrices()
			_ = h.marketRepo.Save(ctx, market)
		}
	}

	result.DurationMs = time.Since(start).Milliseconds()

	h.logger.Info().
		Int64("tick", cmd.TickNumber).
		Int("agents_processed", result.AgentsProcessed).
		Int("agents_died", result.AgentsDied).
		Int("decisions_needed", result.DecisionsNeeded).
		Int64("duration_ms", result.DurationMs).
		Msg("tick processed")

	return result, nil
}

// requestDecisionsAsync requests decisions from the AI Engine without blocking.
func (h *ProcessTickHandler) requestDecisionsAsync(
	ctx context.Context,
	agents []*domain.Agent,
	tick int64,
) {
	decisions, err := h.inferenceClient.GetBatchDecisions(ctx, agents, tick)
	if err != nil {
		h.logger.Error().Err(err).Msg("failed to get decisions from AI Engine")
		// Reset agents to idle on failure
		for _, agent := range agents {
			agent.SetIdle()
			_ = h.agentRepo.Save(ctx, agent)
		}
		return
	}

	// Apply decisions
	for agentID, decision := range decisions {
		agent, err := h.agentRepo.Get(ctx, agentID)
		if err != nil || agent == nil {
			continue
		}

		h.applyDecision(ctx, agent, decision)
	}
}

// applyDecision applies a decision to an agent.
func (h *ProcessTickHandler) applyDecision(
	ctx context.Context,
	agent *domain.Agent,
	decision *domain.ActionDecision,
) {
	agent.SetActing()

	switch decision.ActionType {
	case domain.ActionTypeIdle:
		// Do nothing

	case domain.ActionTypeEat:
		cropTypeStr := decision.Parameters["crop_type"]
		cropType := domain.CropType(cropTypeStr)
		amount := 1.0 // Default amount
		_, _ = agent.Eat(cropType, amount)

	case domain.ActionTypeRest:
		_, _ = agent.Rest()

	case domain.ActionTypeMove:
		if decision.TargetID != nil {
			// Get target market location
			market, err := h.marketRepo.Get(ctx, *decision.TargetID)
			if err == nil && market != nil {
				_ = agent.Move(market.Location)
			}
		}

	case domain.ActionTypeSell:
		if decision.TargetID != nil {
			cropTypeStr := decision.Parameters["crop_type"]
			cropType := domain.CropType(cropTypeStr)
			amount := 10.0 // Default sell amount

			market, err := h.marketRepo.Get(ctx, *decision.TargetID)
			if err == nil && market != nil {
				// Check if agent is near market
				if isNearby(agent.Location, market.Location, 1.0) {
					// Execute sale
					if err := agent.RemoveInventory(cropType, amount); err == nil {
						revenue, err := market.ExecuteSale(cropType, amount)
						if err == nil {
							agent.AddCash(revenue)
							_ = h.marketRepo.Save(ctx, market)
						}
					}
				}
			}
		}

	case domain.ActionTypeBuy:
		if decision.TargetID != nil {
			cropTypeStr := decision.Parameters["crop_type"]
			cropType := domain.CropType(cropTypeStr)
			amount := 5.0 // Default buy amount

			market, err := h.marketRepo.Get(ctx, *decision.TargetID)
			if err == nil && market != nil {
				if isNearby(agent.Location, market.Location, 1.0) {
					cost, err := market.ExecutePurchase(cropType, amount)
					if err == nil {
						if err := agent.SpendCash(cost); err == nil {
							agent.AddInventory(cropType, amount)
							_ = h.marketRepo.Save(ctx, market)
						}
					}
				}
			}
		}
	}

	agent.SetIdle()
	_ = h.agentRepo.Save(ctx, agent)
}

// isNearby checks if two locations are within a given radius (km)
func isNearby(loc1, loc2 domain.Coordinates, radiusKm float64) bool {
	// Simple approximation: 1 degree ≈ 111 km
	latDiff := (loc1.Latitude - loc2.Latitude) * 111
	lonDiff := (loc1.Longitude - loc2.Longitude) * 111
	distance := latDiff*latDiff + lonDiff*lonDiff
	return distance < radiusKm*radiusKm
}

// SpawnAgentCommand represents the command to create a new agent.
type SpawnAgentCommand struct {
	Name           string
	RegionID       uuid.UUID
	Location       domain.Coordinates
	InitialCash    float64
	InitialInventory map[domain.CropType]float64
}

// SpawnAgentHandler handles the SpawnAgent command.
type SpawnAgentHandler struct {
	agentRepo domain.AgentRepository
	logger    zerolog.Logger
}

// NewSpawnAgentHandler creates a new SpawnAgentHandler.
func NewSpawnAgentHandler(
	agentRepo domain.AgentRepository,
	logger zerolog.Logger,
) *SpawnAgentHandler {
	return &SpawnAgentHandler{
		agentRepo: agentRepo,
		logger:    logger,
	}
}

// Handle executes the SpawnAgent command.
func (h *SpawnAgentHandler) Handle(ctx context.Context, cmd SpawnAgentCommand) (*domain.Agent, error) {
	agent := domain.NewAgent(cmd.Name, cmd.RegionID, cmd.Location)
	agent.Cash = cmd.InitialCash

	for cropType, amount := range cmd.InitialInventory {
		agent.AddInventory(cropType, amount)
	}

	if err := h.agentRepo.Save(ctx, agent); err != nil {
		return nil, err
	}

	h.logger.Info().
		Str("agent_id", agent.ID.String()).
		Str("name", agent.Name).
		Msg("agent spawned")

	return agent, nil
}
