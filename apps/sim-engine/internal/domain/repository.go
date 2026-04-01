package domain

import (
	"context"

	"github.com/google/uuid"
)

// AgentRepository defines the interface for agent persistence.
// Following Clean Architecture, this interface is defined in the domain layer
// but implemented in the adapters layer.
type AgentRepository interface {
	// Get retrieves an agent by ID
	Get(ctx context.Context, id uuid.UUID) (*Agent, error)

	// GetAll retrieves all agents
	GetAll(ctx context.Context) ([]*Agent, error)

	// GetByRegion retrieves all agents in a region
	GetByRegion(ctx context.Context, regionID uuid.UUID) ([]*Agent, error)

	// GetByStatus retrieves all agents with a specific status
	GetByStatus(ctx context.Context, status AgentStatus) ([]*Agent, error)

	// GetNearby retrieves agents within a radius (km) of a location
	GetNearby(ctx context.Context, location Coordinates, radiusKm float64) ([]*Agent, error)

	// Save persists an agent (create or update)
	Save(ctx context.Context, agent *Agent) error

	// Delete removes an agent
	Delete(ctx context.Context, id uuid.UUID) error

	// Count returns the total number of agents
	Count(ctx context.Context) (int, error)

	// CountByStatus returns counts grouped by status
	CountByStatus(ctx context.Context) (map[AgentStatus]int, error)
}

// MarketRepository defines the interface for market persistence.
type MarketRepository interface {
	// Get retrieves a market by ID
	Get(ctx context.Context, id uuid.UUID) (*Market, error)

	// GetAll retrieves all markets
	GetAll(ctx context.Context) ([]*Market, error)

	// GetByRegion retrieves all markets in a region
	GetByRegion(ctx context.Context, regionID uuid.UUID) ([]*Market, error)

	// GetNearby retrieves markets within a radius (km) of a location
	GetNearby(ctx context.Context, location Coordinates, radiusKm float64) ([]*Market, error)

	// Save persists a market (create or update)
	Save(ctx context.Context, market *Market) error

	// Delete removes a market
	Delete(ctx context.Context, id uuid.UUID) error

	// Count returns the total number of markets
	Count(ctx context.Context) (int, error)
}

// RegionRepository defines the interface for region persistence.
type RegionRepository interface {
	// Get retrieves a region by ID
	Get(ctx context.Context, id uuid.UUID) (*Region, error)

	// GetByCode retrieves a region by administrative code
	GetByCode(ctx context.Context, code string) (*Region, error)

	// GetAll retrieves all regions
	GetAll(ctx context.Context) ([]*Region, error)

	// GetChildren retrieves child regions of a parent
	GetChildren(ctx context.Context, parentID uuid.UUID) ([]*Region, error)

	// Save persists a region (create or update)
	Save(ctx context.Context, region *Region) error

	// Delete removes a region
	Delete(ctx context.Context, id uuid.UUID) error

	// Count returns the total number of regions
	Count(ctx context.Context) (int, error)
}

// ActionDecision represents a decision from the AI inference service
type ActionDecision struct {
	AgentID    uuid.UUID
	ActionType ActionType
	TargetID   *uuid.UUID        // Optional target (market, location)
	Parameters map[string]string // Action-specific parameters
	Reasoning  string
	Confidence float64
	Tick       int64
}

// InferenceClient defines the interface for AI inference requests.
// This abstracts the gRPC communication with the Python AI Engine.
type InferenceClient interface {
	// GetDecision requests a decision for a single agent
	GetDecision(ctx context.Context, agent *Agent, tick int64) (*ActionDecision, error)

	// GetBatchDecisions requests decisions for multiple agents
	GetBatchDecisions(ctx context.Context, agents []*Agent, tick int64) (map[uuid.UUID]*ActionDecision, error)

	// HealthCheck verifies the inference service is available
	HealthCheck(ctx context.Context) error

	// Close releases resources
	Close() error
}
