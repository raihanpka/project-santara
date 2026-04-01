// Package inference provides the gRPC client for the Python AI Engine.
// This adapter implements domain.InferenceClient for communication
// with the Inference Gateway.
package inference

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"

	"github.com/santara/sim-engine/internal/domain"
)

// GRPCInferenceClient implements domain.InferenceClient using gRPC.
type GRPCInferenceClient struct {
	conn   *grpc.ClientConn
	// client simulationv1.InferenceServiceClient // Uncomment when proto is compiled
	logger zerolog.Logger
	config ClientConfig
}

// ClientConfig holds configuration for the gRPC client.
type ClientConfig struct {
	Address     string
	Timeout     time.Duration
	MaxRetries  int
	RetryDelay  time.Duration
	KeepAlive   time.Duration
}

// DefaultClientConfig returns default client configuration.
func DefaultClientConfig() ClientConfig {
	return ClientConfig{
		Address:    "localhost:50051",
		Timeout:    30 * time.Second,
		MaxRetries: 3,
		RetryDelay: 1 * time.Second,
		KeepAlive:  30 * time.Second,
	}
}

// NewGRPCInferenceClient creates a new gRPC inference client.
func NewGRPCInferenceClient(config ClientConfig, logger zerolog.Logger) (*GRPCInferenceClient, error) {
	// Setup keepalive parameters
	kaParams := keepalive.ClientParameters{
		Time:                config.KeepAlive,
		Timeout:             10 * time.Second,
		PermitWithoutStream: true,
	}

	// Connect to gRPC server
	conn, err := grpc.NewClient(
		config.Address,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithKeepaliveParams(kaParams),
	)
	if err != nil {
		return nil, err
	}

	client := &GRPCInferenceClient{
		conn:   conn,
		// client: simulationv1.NewInferenceServiceClient(conn),
		logger: logger,
		config: config,
	}

	logger.Info().Str("address", config.Address).Msg("gRPC inference client created")

	return client, nil
}

// GetDecision requests a decision for a single agent.
func (c *GRPCInferenceClient) GetDecision(
	ctx context.Context,
	agent *domain.Agent,
	tick int64,
) (*domain.ActionDecision, error) {
	// Convert domain agent to protobuf
	// req := &simulationv1.GetDecisionRequest{
	// 	Agent:       agentToProto(agent),
	// 	CurrentTick: tick,
	// }

	// Create context with timeout
	ctx, cancel := context.WithTimeout(ctx, c.config.Timeout)
	defer cancel()

	// Call the service
	// resp, err := c.client.GetDecision(ctx, req)
	// if err != nil {
	// 	return nil, err
	// }

	// Convert response to domain
	// return protoToDecision(resp.Decision), nil

	// Placeholder implementation until proto is compiled
	c.logger.Debug().
		Str("agent_id", agent.ID.String()).
		Int64("tick", tick).
		Msg("get_decision called (stub)")

	// Return a default decision for now
	return &domain.ActionDecision{
		AgentID:    agent.ID,
		ActionType: domain.ActionTypeIdle,
		Reasoning:  "Stub decision - inference client not fully connected",
		Confidence: 0.5,
		Tick:       tick,
	}, nil
}

// GetBatchDecisions requests decisions for multiple agents.
func (c *GRPCInferenceClient) GetBatchDecisions(
	ctx context.Context,
	agents []*domain.Agent,
	tick int64,
) (map[uuid.UUID]*domain.ActionDecision, error) {
	// Convert domain agents to protobuf
	// protoAgents := make([]*simulationv1.AgentState, len(agents))
	// for i, agent := range agents {
	// 	protoAgents[i] = agentToProto(agent)
	// }

	// req := &simulationv1.GetBatchDecisionsRequest{
	// 	Agents:      protoAgents,
	// 	CurrentTick: tick,
	// }

	// Create context with timeout
	ctx, cancel := context.WithTimeout(ctx, c.config.Timeout)
	defer cancel()

	// Call the service
	// resp, err := c.client.GetBatchDecisions(ctx, req)
	// if err != nil {
	// 	return nil, err
	// }

	// Convert response to domain
	// decisions := make(map[uuid.UUID]*domain.ActionDecision)
	// for agentID, protoDecision := range resp.Decisions {
	// 	id, _ := uuid.Parse(agentID)
	// 	decisions[id] = protoToDecision(protoDecision)
	// }
	// return decisions, nil

	// Placeholder implementation until proto is compiled
	c.logger.Debug().
		Int("agent_count", len(agents)).
		Int64("tick", tick).
		Msg("get_batch_decisions called (stub)")

	decisions := make(map[uuid.UUID]*domain.ActionDecision)
	for _, agent := range agents {
		decisions[agent.ID] = &domain.ActionDecision{
			AgentID:    agent.ID,
			ActionType: domain.ActionTypeIdle,
			Reasoning:  "Stub decision - inference client not fully connected",
			Confidence: 0.5,
			Tick:       tick,
		}
	}

	return decisions, nil
}

// HealthCheck verifies the inference service is available.
func (c *GRPCInferenceClient) HealthCheck(ctx context.Context) error {
	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	// Call health check
	// _, err := c.client.HealthCheck(ctx, &simulationv1.HealthCheckRequest{})
	// return err

	c.logger.Debug().Msg("health_check called (stub)")
	return nil
}

// Close releases resources.
func (c *GRPCInferenceClient) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// Conversion functions (to be implemented when proto is compiled)

// func agentToProto(agent *domain.Agent) *simulationv1.AgentState {
// 	inventory := make(map[int32]float64)
// 	for crop, qty := range agent.Inventory {
// 		inventory[cropTypeToProto(crop)] = qty
// 	}
//
// 	return &simulationv1.AgentState{
// 		Id:        agent.ID.String(),
// 		Name:      agent.Name,
// 		RegionId:  agent.RegionID.String(),
// 		Status:    agentStatusToProto(agent.Status),
// 		Cash:      agent.Cash,
// 		Inventory: &simulationv1.Inventory{Items: inventory},
// 		LandSize:  agent.LandSize,
// 		Health:    agent.Health,
// 		Hunger:    agent.Hunger,
// 		Location: &simulationv1.Coordinates{
// 			Latitude:  agent.Location.Latitude,
// 			Longitude: agent.Location.Longitude,
// 		},
// 	}
// }

// func protoToDecision(proto *simulationv1.ActionDecision) *domain.ActionDecision {
// 	agentID, _ := uuid.Parse(proto.AgentId)
//
// 	var targetID *uuid.UUID
// 	if proto.TargetId != "" {
// 		id, _ := uuid.Parse(proto.TargetId)
// 		targetID = &id
// 	}
//
// 	return &domain.ActionDecision{
// 		AgentID:    agentID,
// 		ActionType: protoToActionType(proto.ActionType),
// 		TargetID:   targetID,
// 		Parameters: proto.Parameters,
// 		Reasoning:  proto.Reasoning,
// 		Confidence: proto.Confidence,
// 		Tick:       proto.Tick,
// 	}
// }

// MockInferenceClient provides a mock implementation for testing.
type MockInferenceClient struct {
	Decisions map[uuid.UUID]*domain.ActionDecision
	Error     error
}

// NewMockInferenceClient creates a new mock inference client.
func NewMockInferenceClient() *MockInferenceClient {
	return &MockInferenceClient{
		Decisions: make(map[uuid.UUID]*domain.ActionDecision),
	}
}

// GetDecision returns a mock decision.
func (m *MockInferenceClient) GetDecision(
	ctx context.Context,
	agent *domain.Agent,
	tick int64,
) (*domain.ActionDecision, error) {
	if m.Error != nil {
		return nil, m.Error
	}

	if decision, ok := m.Decisions[agent.ID]; ok {
		return decision, nil
	}

	return &domain.ActionDecision{
		AgentID:    agent.ID,
		ActionType: domain.ActionTypeIdle,
		Reasoning:  "Mock decision",
		Confidence: 1.0,
		Tick:       tick,
	}, nil
}

// GetBatchDecisions returns mock decisions for multiple agents.
func (m *MockInferenceClient) GetBatchDecisions(
	ctx context.Context,
	agents []*domain.Agent,
	tick int64,
) (map[uuid.UUID]*domain.ActionDecision, error) {
	if m.Error != nil {
		return nil, m.Error
	}

	decisions := make(map[uuid.UUID]*domain.ActionDecision)
	for _, agent := range agents {
		if decision, ok := m.Decisions[agent.ID]; ok {
			decisions[agent.ID] = decision
		} else {
			decisions[agent.ID] = &domain.ActionDecision{
				AgentID:    agent.ID,
				ActionType: domain.ActionTypeIdle,
				Reasoning:  "Mock decision",
				Confidence: 1.0,
				Tick:       tick,
			}
		}
	}

	return decisions, nil
}

// HealthCheck always returns nil for mock.
func (m *MockInferenceClient) HealthCheck(ctx context.Context) error {
	return m.Error
}

// Close is a no-op for mock.
func (m *MockInferenceClient) Close() error {
	return nil
}

// SetDecision sets a mock decision for an agent.
func (m *MockInferenceClient) SetDecision(agentID uuid.UUID, decision *domain.ActionDecision) {
	m.Decisions[agentID] = decision
}
