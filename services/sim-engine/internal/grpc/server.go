// Package grpcserver implements the SimulationService gRPC interface.
package grpcserver

import (
	"context"
	"errors"

	"github.com/google/uuid"
	"github.com/rs/zerolog"

	"github.com/raihanpka/project-santara/services/sim-engine/internal/app"
	pb "github.com/raihanpka/project-santara/services/sim-engine/internal/grpc_gen"
	"github.com/raihanpka/project-santara/services/sim-engine/internal/state"
)

// Server is the gRPC service implementation.
type Server struct {
	pb.UnimplementedSimulationServiceServer
	store  *state.Store
	engine *app.TickEngine
	log    zerolog.Logger
}

// New wires the gRPC server to its dependencies.
func New(store *state.Store, engine *app.TickEngine, log zerolog.Logger) *Server {
	return &Server{store: store, engine: engine, log: log}
}

func (s *Server) CreateSimulation(ctx context.Context, req *pb.CreateSimulationRequest) (*pb.CreateSimulationResponse, error) {
	id := uuid.NewString()
	sim, err := s.store.Create(id, req.ScenarioId, req.Locale, req.Seed, req.InitialState)
	if err != nil {
		return nil, err
	}
	s.log.Info().Str("sim", sim.ID).Str("scenario", sim.ScenarioID).Msg("simulation created")
	return &pb.CreateSimulationResponse{
		SimulationId: sim.ID,
		InitialState: sim.ToWorldState(),
	}, nil
}

func (s *Server) DestroySimulation(ctx context.Context, req *pb.DestroySimulationRequest) (*pb.DestroySimulationResponse, error) {
	if err := s.store.Destroy(req.SimulationId); err != nil {
		return nil, err
	}
	s.log.Info().Str("sim", req.SimulationId).Msg("simulation destroyed")
	return &pb.DestroySimulationResponse{}, nil
}

func (s *Server) SpawnAgent(ctx context.Context, req *pb.SpawnAgentRequest) (*pb.SpawnAgentResponse, error) {
	sim, err := s.store.Get(req.SimulationId)
	if err != nil {
		return nil, err
	}
	sim.Mu.Lock()
	defer sim.Mu.Unlock()
	agentID := uuid.NewString()
	sim.Agents[agentID] = &pb.Agent{
		Id:     agentID,
		Kind:   req.Kind,
		Locale: req.Locale,
		State:  req.InitialState,
	}
	s.log.Info().Str("sim", sim.ID).Str("agent", agentID).Str("kind", req.Kind).Msg("agent spawned")
	return &pb.SpawnAgentResponse{AgentId: agentID}, nil
}

func (s *Server) KillAgent(ctx context.Context, req *pb.KillAgentRequest) (*pb.KillAgentResponse, error) {
	sim, err := s.store.Get(req.SimulationId)
	if err != nil {
		return nil, err
	}
	sim.Mu.Lock()
	defer sim.Mu.Unlock()
	if _, ok := sim.Agents[req.AgentId]; !ok {
		return nil, errors.New("agent not found")
	}
	delete(sim.Agents, req.AgentId)
	s.log.Info().Str("sim", sim.ID).Str("agent", req.AgentId).Msg("agent killed")
	return &pb.KillAgentResponse{}, nil
}

func (s *Server) RunTicks(ctx context.Context, req *pb.RunTicksRequest) (*pb.RunTicksResponse, error) {
	ws, err := s.engine.Run(ctx, req.SimulationId, req.Count)
	if err != nil {
		return nil, err
	}
	return &pb.RunTicksResponse{FinalState: ws}, nil
}

func (s *Server) Pause(ctx context.Context, req *pb.PauseRequest) (*pb.PauseResponse, error) {
	if err := s.engine.Pause(ctx, req.SimulationId); err != nil {
		return nil, err
	}
	return &pb.PauseResponse{}, nil
}

func (s *Server) Resume(ctx context.Context, req *pb.ResumeRequest) (*pb.ResumeResponse, error) {
	if err := s.engine.Resume(ctx, req.SimulationId); err != nil {
		return nil, err
	}
	return &pb.ResumeResponse{}, nil
}

func (s *Server) GetWorldState(ctx context.Context, req *pb.GetWorldStateRequest) (*pb.WorldState, error) {
	sim, err := s.store.Get(req.SimulationId)
	if err != nil {
		return nil, err
	}
	return sim.ToWorldState(), nil
}

func (s *Server) ApplyShock(ctx context.Context, req *pb.ApplyShockRequest) (*pb.ApplyShockResponse, error) {
	if req.Shock == nil {
		return nil, errors.New("shock is required")
	}
	ws, err := s.engine.ApplyShock(ctx, req.Shock.SimulationId, req.Shock)
	if err != nil {
		return nil, err
	}
	return &pb.ApplyShockResponse{AfterShock: ws}, nil
}
