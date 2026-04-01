// Package state provides in-memory state management for the simulation.
// This is an adapter implementing the domain repository interfaces.
package state

import (
	"context"
	"math"
	"sync"

	"github.com/google/uuid"

	"github.com/santara/sim-engine/internal/domain"
)

// InMemoryAgentRepository implements domain.AgentRepository with in-memory storage.
// Optimized for high-speed simulation access with proper synchronization.
type InMemoryAgentRepository struct {
	mu     sync.RWMutex
	agents map[uuid.UUID]*domain.Agent

	// Index for efficient lookups
	byRegion map[uuid.UUID]map[uuid.UUID]struct{}
	byStatus map[domain.AgentStatus]map[uuid.UUID]struct{}
}

// NewInMemoryAgentRepository creates a new in-memory agent repository.
func NewInMemoryAgentRepository() *InMemoryAgentRepository {
	return &InMemoryAgentRepository{
		agents:   make(map[uuid.UUID]*domain.Agent),
		byRegion: make(map[uuid.UUID]map[uuid.UUID]struct{}),
		byStatus: make(map[domain.AgentStatus]map[uuid.UUID]struct{}),
	}
}

// Get retrieves an agent by ID.
func (r *InMemoryAgentRepository) Get(ctx context.Context, id uuid.UUID) (*domain.Agent, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	agent, ok := r.agents[id]
	if !ok {
		return nil, nil
	}

	return agent, nil // Return direct reference for performance
}

// GetAll retrieves all agents.
func (r *InMemoryAgentRepository) GetAll(ctx context.Context) ([]*domain.Agent, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*domain.Agent, 0, len(r.agents))
	for _, agent := range r.agents {
		result = append(result, agent)
	}

	return result, nil
}

// GetByRegion retrieves all agents in a region.
func (r *InMemoryAgentRepository) GetByRegion(ctx context.Context, regionID uuid.UUID) ([]*domain.Agent, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	agentIDs, ok := r.byRegion[regionID]
	if !ok {
		return []*domain.Agent{}, nil
	}

	result := make([]*domain.Agent, 0, len(agentIDs))
	for id := range agentIDs {
		if agent, ok := r.agents[id]; ok {
			result = append(result, agent)
		}
	}

	return result, nil
}

// GetByStatus retrieves all agents with a specific status.
func (r *InMemoryAgentRepository) GetByStatus(ctx context.Context, status domain.AgentStatus) ([]*domain.Agent, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	agentIDs, ok := r.byStatus[status]
	if !ok {
		return []*domain.Agent{}, nil
	}

	result := make([]*domain.Agent, 0, len(agentIDs))
	for id := range agentIDs {
		if agent, ok := r.agents[id]; ok {
			result = append(result, agent)
		}
	}

	return result, nil
}

// GetNearby retrieves agents within a radius of a location.
func (r *InMemoryAgentRepository) GetNearby(ctx context.Context, location domain.Coordinates, radiusKm float64) ([]*domain.Agent, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*domain.Agent, 0)
	for _, agent := range r.agents {
		if agent.Status == domain.AgentStatusDead {
			continue
		}

		dist := haversineDistance(
			location.Latitude, location.Longitude,
			agent.Location.Latitude, agent.Location.Longitude,
		)

		if dist <= radiusKm {
			result = append(result, agent)
		}
	}

	return result, nil
}

// Save persists an agent (create or update).
func (r *InMemoryAgentRepository) Save(ctx context.Context, agent *domain.Agent) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Remove from old indexes if updating
	if existing, ok := r.agents[agent.ID]; ok {
		r.removeFromIndexes(existing)
	}

	// Store agent
	r.agents[agent.ID] = agent

	// Add to indexes
	r.addToIndexes(agent)

	return nil
}

// Delete removes an agent.
func (r *InMemoryAgentRepository) Delete(ctx context.Context, id uuid.UUID) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	agent, ok := r.agents[id]
	if !ok {
		return nil
	}

	r.removeFromIndexes(agent)
	delete(r.agents, id)

	return nil
}

// Count returns the total number of agents.
func (r *InMemoryAgentRepository) Count(ctx context.Context) (int, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return len(r.agents), nil
}

// CountByStatus returns counts grouped by status.
func (r *InMemoryAgentRepository) CountByStatus(ctx context.Context) (map[domain.AgentStatus]int, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	counts := make(map[domain.AgentStatus]int)
	for status, ids := range r.byStatus {
		counts[status] = len(ids)
	}

	return counts, nil
}

// addToIndexes adds an agent to all indexes.
func (r *InMemoryAgentRepository) addToIndexes(agent *domain.Agent) {
	// Region index
	if _, ok := r.byRegion[agent.RegionID]; !ok {
		r.byRegion[agent.RegionID] = make(map[uuid.UUID]struct{})
	}
	r.byRegion[agent.RegionID][agent.ID] = struct{}{}

	// Status index
	if _, ok := r.byStatus[agent.Status]; !ok {
		r.byStatus[agent.Status] = make(map[uuid.UUID]struct{})
	}
	r.byStatus[agent.Status][agent.ID] = struct{}{}
}

// removeFromIndexes removes an agent from all indexes.
func (r *InMemoryAgentRepository) removeFromIndexes(agent *domain.Agent) {
	// Region index
	if ids, ok := r.byRegion[agent.RegionID]; ok {
		delete(ids, agent.ID)
	}

	// Status index - remove from all statuses (in case status changed)
	for _, ids := range r.byStatus {
		delete(ids, agent.ID)
	}
}

// InMemoryMarketRepository implements domain.MarketRepository with in-memory storage.
type InMemoryMarketRepository struct {
	mu      sync.RWMutex
	markets map[uuid.UUID]*domain.Market

	// Index for efficient lookups
	byRegion map[uuid.UUID]map[uuid.UUID]struct{}
}

// NewInMemoryMarketRepository creates a new in-memory market repository.
func NewInMemoryMarketRepository() *InMemoryMarketRepository {
	return &InMemoryMarketRepository{
		markets:  make(map[uuid.UUID]*domain.Market),
		byRegion: make(map[uuid.UUID]map[uuid.UUID]struct{}),
	}
}

// Get retrieves a market by ID.
func (r *InMemoryMarketRepository) Get(ctx context.Context, id uuid.UUID) (*domain.Market, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	market, ok := r.markets[id]
	if !ok {
		return nil, nil
	}

	return market, nil
}

// GetAll retrieves all markets.
func (r *InMemoryMarketRepository) GetAll(ctx context.Context) ([]*domain.Market, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*domain.Market, 0, len(r.markets))
	for _, market := range r.markets {
		result = append(result, market)
	}

	return result, nil
}

// GetByRegion retrieves all markets in a region.
func (r *InMemoryMarketRepository) GetByRegion(ctx context.Context, regionID uuid.UUID) ([]*domain.Market, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	marketIDs, ok := r.byRegion[regionID]
	if !ok {
		return []*domain.Market{}, nil
	}

	result := make([]*domain.Market, 0, len(marketIDs))
	for id := range marketIDs {
		if market, ok := r.markets[id]; ok {
			result = append(result, market)
		}
	}

	return result, nil
}

// GetNearby retrieves markets within a radius of a location.
func (r *InMemoryMarketRepository) GetNearby(ctx context.Context, location domain.Coordinates, radiusKm float64) ([]*domain.Market, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*domain.Market, 0)
	for _, market := range r.markets {
		dist := haversineDistance(
			location.Latitude, location.Longitude,
			market.Location.Latitude, market.Location.Longitude,
		)

		if dist <= radiusKm {
			result = append(result, market)
		}
	}

	return result, nil
}

// Save persists a market (create or update).
func (r *InMemoryMarketRepository) Save(ctx context.Context, market *domain.Market) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Remove from old indexes if updating
	if existing, ok := r.markets[market.ID]; ok {
		if ids, ok := r.byRegion[existing.RegionID]; ok {
			delete(ids, market.ID)
		}
	}

	// Store market
	r.markets[market.ID] = market

	// Add to region index
	if _, ok := r.byRegion[market.RegionID]; !ok {
		r.byRegion[market.RegionID] = make(map[uuid.UUID]struct{})
	}
	r.byRegion[market.RegionID][market.ID] = struct{}{}

	return nil
}

// Delete removes a market.
func (r *InMemoryMarketRepository) Delete(ctx context.Context, id uuid.UUID) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	market, ok := r.markets[id]
	if !ok {
		return nil
	}

	if ids, ok := r.byRegion[market.RegionID]; ok {
		delete(ids, id)
	}
	delete(r.markets, id)

	return nil
}

// Count returns the total number of markets.
func (r *InMemoryMarketRepository) Count(ctx context.Context) (int, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return len(r.markets), nil
}

// InMemoryRegionRepository implements domain.RegionRepository with in-memory storage.
type InMemoryRegionRepository struct {
	mu      sync.RWMutex
	regions map[uuid.UUID]*domain.Region

	// Index for efficient lookups
	byCode   map[string]uuid.UUID
	byParent map[uuid.UUID]map[uuid.UUID]struct{}
}

// NewInMemoryRegionRepository creates a new in-memory region repository.
func NewInMemoryRegionRepository() *InMemoryRegionRepository {
	return &InMemoryRegionRepository{
		regions:  make(map[uuid.UUID]*domain.Region),
		byCode:   make(map[string]uuid.UUID),
		byParent: make(map[uuid.UUID]map[uuid.UUID]struct{}),
	}
}

// Get retrieves a region by ID.
func (r *InMemoryRegionRepository) Get(ctx context.Context, id uuid.UUID) (*domain.Region, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	region, ok := r.regions[id]
	if !ok {
		return nil, nil
	}

	return region, nil
}

// GetByCode retrieves a region by administrative code.
func (r *InMemoryRegionRepository) GetByCode(ctx context.Context, code string) (*domain.Region, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	id, ok := r.byCode[code]
	if !ok {
		return nil, nil
	}

	return r.regions[id], nil
}

// GetAll retrieves all regions.
func (r *InMemoryRegionRepository) GetAll(ctx context.Context) ([]*domain.Region, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*domain.Region, 0, len(r.regions))
	for _, region := range r.regions {
		result = append(result, region)
	}

	return result, nil
}

// GetChildren retrieves child regions of a parent.
func (r *InMemoryRegionRepository) GetChildren(ctx context.Context, parentID uuid.UUID) ([]*domain.Region, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	childIDs, ok := r.byParent[parentID]
	if !ok {
		return []*domain.Region{}, nil
	}

	result := make([]*domain.Region, 0, len(childIDs))
	for id := range childIDs {
		if region, ok := r.regions[id]; ok {
			result = append(result, region)
		}
	}

	return result, nil
}

// Save persists a region (create or update).
func (r *InMemoryRegionRepository) Save(ctx context.Context, region *domain.Region) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	// Remove from old indexes if updating
	if existing, ok := r.regions[region.ID]; ok {
		delete(r.byCode, existing.Code)
		if existing.ParentID != nil {
			if ids, ok := r.byParent[*existing.ParentID]; ok {
				delete(ids, region.ID)
			}
		}
	}

	// Store region
	r.regions[region.ID] = region

	// Add to indexes
	r.byCode[region.Code] = region.ID

	if region.ParentID != nil {
		if _, ok := r.byParent[*region.ParentID]; !ok {
			r.byParent[*region.ParentID] = make(map[uuid.UUID]struct{})
		}
		r.byParent[*region.ParentID][region.ID] = struct{}{}
	}

	return nil
}

// Delete removes a region.
func (r *InMemoryRegionRepository) Delete(ctx context.Context, id uuid.UUID) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	region, ok := r.regions[id]
	if !ok {
		return nil
	}

	delete(r.byCode, region.Code)
	if region.ParentID != nil {
		if ids, ok := r.byParent[*region.ParentID]; ok {
			delete(ids, id)
		}
	}
	delete(r.regions, id)

	return nil
}

// Count returns the total number of regions.
func (r *InMemoryRegionRepository) Count(ctx context.Context) (int, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return len(r.regions), nil
}

// haversineDistance calculates the great-circle distance between two points in kilometers.
func haversineDistance(lat1, lon1, lat2, lon2 float64) float64 {
	const earthRadiusKm = 6371.0

	lat1Rad := lat1 * math.Pi / 180
	lat2Rad := lat2 * math.Pi / 180
	deltaLat := (lat2 - lat1) * math.Pi / 180
	deltaLon := (lon2 - lon1) * math.Pi / 180

	a := math.Sin(deltaLat/2)*math.Sin(deltaLat/2) +
		math.Cos(lat1Rad)*math.Cos(lat2Rad)*
			math.Sin(deltaLon/2)*math.Sin(deltaLon/2)

	c := 2 * math.Atan2(math.Sqrt(a), math.Sqrt(1-a))

	return earthRadiusKm * c
}
