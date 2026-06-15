// Package state is the in-memory simulation store.
//
// ponytail: map + RWMutex, no ORM, no database in v1.0. PostgreSQL via pgx
// is planned for v1.5.0 once we have persistence requirements that justify
// the operational cost.
package state

import (
	"errors"
	"sync"

	pb "github.com/raihanpka/sim-engine/internal/grpc_gen"
)

// ErrNotFound is returned when a simulation or agent does not exist.
var ErrNotFound = errors.New("simulation not found")

// Simulation holds the live state of one running counterfactual scenario.
type Simulation struct {
	ID         string
	ScenarioID string
	Locale     string
	Seed       int64
	Tick       uint64
	Paused     bool
	Agents     map[string]*pb.Agent
	Macro      map[string]float64
	Mu         sync.RWMutex
}

// Store is the thread-safe in-memory registry of simulations.
type Store struct {
	mu        sync.RWMutex
	sims      map[string]*Simulation
	maxSims   int
	maxAgents int
}

// NewStore creates an empty store with the given caps.
func NewStore(maxSims, maxAgents int) *Store {
	return &Store{
		sims:      make(map[string]*Simulation),
		maxSims:   maxSims,
		maxAgents: maxAgents,
	}
}

// Create registers a new simulation and returns it.
func (s *Store) Create(id, scenarioID, locale string, seed int64, initial map[string]float64) (*Simulation, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.sims) >= s.maxSims {
		return nil, errors.New("max simulations reached")
	}
	sim := &Simulation{
		ID:         id,
		ScenarioID: scenarioID,
		Locale:     locale,
		Seed:       seed,
		Agents:     make(map[string]*pb.Agent),
		Macro:      copyMap(initial),
	}
	s.sims[id] = sim
	return sim, nil
}

// Get returns a simulation by ID, or ErrNotFound.
func (s *Store) Get(id string) (*Simulation, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	sim, ok := s.sims[id]
	if !ok {
		return nil, ErrNotFound
	}
	return sim, nil
}

// Destroy removes a simulation by ID.
func (s *Store) Destroy(id string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.sims[id]; !ok {
		return ErrNotFound
	}
	delete(s.sims, id)
	return nil
}

// Count returns the number of live simulations.
func (s *Store) Count() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.sims)
}

func copyMap(in map[string]float64) map[string]float64 {
	out := make(map[string]float64, len(in))
	for k, v := range in {
		out[k] = v
	}
	return out
}

// ToWorldState returns a snapshot WorldState for the simulation.
//
// ponytail: single read lock, copy under lock, no surprises for callers.
func (sim *Simulation) ToWorldState() *pb.WorldState {
	sim.Mu.RLock()
	defer sim.Mu.RUnlock()
	return sim.ToWorldStateLocked()
}

// ToWorldStateLocked returns a snapshot without locking. The caller must
// already hold sim.Mu (read or write). Used by hot paths that already
// hold the write lock and would otherwise deadlock on sync.RWMutex's
// non-reentrant semantics.
func (sim *Simulation) ToWorldStateLocked() *pb.WorldState {
	agents := make([]*pb.Agent, 0, len(sim.Agents))
	for _, a := range sim.Agents {
		agents = append(agents, a)
	}
	return &pb.WorldState{
		SimulationId:    sim.ID,
		Tick:            sim.Tick,
		Agents:          agents,
		MacroIndicators: copyMap(sim.Macro),
	}
}
