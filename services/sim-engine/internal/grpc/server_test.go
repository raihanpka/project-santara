// In-process gRPC test for sim-engine.
//
// ponytail: bufconn, no real socket, no docker, no flake. The whole service
// runs in one process for the test.
package grpcserver

import (
	"context"
	"net"
	"testing"
	"time"

	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"github.com/raihanpka/project-santara/services/sim-engine/internal/app"
	pb "github.com/raihanpka/project-santara/services/sim-engine/internal/grpc_gen"
	"github.com/raihanpka/project-santara/services/sim-engine/internal/state"
)

func newTestServer(t *testing.T) (pb.SimulationServiceClient, *state.Store) {
	t.Helper()
	store := state.NewStore(64, 1024)
	engine := app.NewTickEngine(store)
	log := zerolog.Nop()
	srv := New(store, engine, log)

	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	g := grpc.NewServer()
	pb.RegisterSimulationServiceServer(g, srv)
	go func() {
		_ = g.Serve(lis)
	}()

	conn, err := grpc.NewClient(
		lis.Addr().String(),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("grpc.NewClient: %v", err)
	}
	t.Cleanup(func() {
		_ = conn.Close()
		g.Stop()
		_ = lis.Close()
	})
	return pb.NewSimulationServiceClient(conn), store
}

func TestCreateAndDestroySimulation(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	c, store := newTestServer(t)

	resp, err := c.CreateSimulation(ctx, &pb.CreateSimulationRequest{
		ScenarioId: "pertamax_30pct",
		Locale:     "id-JK",
		Seed:       42,
		InitialState: map[string]float64{
			"cpi_yoy_pct":     2.5,
			"bi_rate_pct":     6.0,
			"usd_idr":         16200.0,
			"pertamax_idr_pl": 12300.0,
		},
	})
	if err != nil {
		t.Fatalf("CreateSimulation: %v", err)
	}
	if resp.SimulationId == "" {
		t.Fatal("expected non-empty simulation id")
	}
	if resp.InitialState.Tick != 0 {
		t.Fatalf("expected tick=0, got %d", resp.InitialState.Tick)
	}
	if v := resp.InitialState.MacroIndicators["bi_rate_pct"]; v != 6.0 {
		t.Fatalf("expected bi_rate_pct=6.0, got %v", v)
	}
	if store.Count() != 1 {
		t.Fatalf("expected 1 simulation, got %d", store.Count())
	}

	if _, err := c.DestroySimulation(ctx, &pb.DestroySimulationRequest{
		SimulationId: resp.SimulationId,
	}); err != nil {
		t.Fatalf("DestroySimulation: %v", err)
	}
	if store.Count() != 0 {
		t.Fatalf("expected 0 simulations after destroy, got %d", store.Count())
	}
}

func TestRunTicksAndPauseResume(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	c, _ := newTestServer(t)

	r, err := c.CreateSimulation(ctx, &pb.CreateSimulationRequest{
		ScenarioId: "test", Locale: "id", Seed: 1,
	})
	if err != nil {
		t.Fatal(err)
	}
	id := r.SimulationId

	r1, err := c.RunTicks(ctx, &pb.RunTicksRequest{SimulationId: id, Count: 5})
	if err != nil {
		t.Fatal(err)
	}
	if r1.FinalState.Tick != 5 {
		t.Fatalf("expected tick=5, got %d", r1.FinalState.Tick)
	}

	if _, err := c.Pause(ctx, &pb.PauseRequest{SimulationId: id}); err != nil {
		t.Fatal(err)
	}
	r2, err := c.RunTicks(ctx, &pb.RunTicksRequest{SimulationId: id, Count: 5})
	if err != nil {
		t.Fatal(err)
	}
	if r2.FinalState.Tick != 5 {
		t.Fatalf("expected tick still=5 while paused, got %d", r2.FinalState.Tick)
	}

	if _, err := c.Resume(ctx, &pb.ResumeRequest{SimulationId: id}); err != nil {
		t.Fatal(err)
	}
	r3, err := c.RunTicks(ctx, &pb.RunTicksRequest{SimulationId: id, Count: 3})
	if err != nil {
		t.Fatal(err)
	}
	if r3.FinalState.Tick != 8 {
		t.Fatalf("expected tick=8 after resume, got %d", r3.FinalState.Tick)
	}
}

func TestSpawnAndKillAgent(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	c, _ := newTestServer(t)
	r, err := c.CreateSimulation(ctx, &pb.CreateSimulationRequest{ScenarioId: "test", Locale: "id", Seed: 1})
	if err != nil {
		t.Fatal(err)
	}
	id := r.SimulationId

	ar, err := c.SpawnAgent(ctx, &pb.SpawnAgentRequest{
		SimulationId: id, Kind: "household", Locale: "id-JK",
		InitialState: map[string]float64{
			"income_idr":  5_000_000,
			"household_n": 4,
		},
	})
	if err != nil {
		t.Fatal(err)
	}

	ws, err := c.GetWorldState(ctx, &pb.GetWorldStateRequest{SimulationId: id})
	if err != nil {
		t.Fatal(err)
	}
	if len(ws.Agents) != 1 {
		t.Fatalf("expected 1 agent, got %d", len(ws.Agents))
	}

	if _, err := c.KillAgent(ctx, &pb.KillAgentRequest{SimulationId: id, AgentId: ar.AgentId}); err != nil {
		t.Fatal(err)
	}
	ws2, err := c.GetWorldState(ctx, &pb.GetWorldStateRequest{SimulationId: id})
	if err != nil {
		t.Fatal(err)
	}
	if len(ws2.Agents) != 0 {
		t.Fatalf("expected 0 agents after kill, got %d", len(ws2.Agents))
	}
}

func TestApplyFiscalShock(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	c, _ := newTestServer(t)
	r, err := c.CreateSimulation(ctx, &pb.CreateSimulationRequest{ScenarioId: "test", Locale: "id", Seed: 1})
	if err != nil {
		t.Fatal(err)
	}
	id := r.SimulationId

	ar, err := c.ApplyShock(ctx, &pb.ApplyShockRequest{
		Shock: &pb.Shock{
			SimulationId: id,
			Kind: &pb.Shock_Fiscal{Fiscal: &pb.FiscalShock{
				PertamaxPriceChangePct:  30.0,
				PertalitePriceChangePct: 0,
				SolarPriceChangePct:     0,
				BiRateChangeBps:         25,
				SubsidiChangePct:        -10,
				ExchangeRateShockPct:    0,
			}},
		},
	})
	if err != nil {
		t.Fatal(err)
	}
	if v := ar.AfterShock.MacroIndicators["pertamax_price_change_pct"]; v != 30.0 {
		t.Fatalf("expected pertamax shock=30, got %v", v)
	}
	if v := ar.AfterShock.MacroIndicators["bi_rate_change_bps"]; v != 25.0 {
		t.Fatalf("expected bi_rate_change_bps=25, got %v", v)
	}
}
