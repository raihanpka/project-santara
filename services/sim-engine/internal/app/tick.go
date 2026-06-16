// Package app is the use-case layer. The tick engine lives here.
//
// ponytail: the v0.1.0 tick is a counter. The v0.2.0 tick will apply
// market dynamics, agent decisions, and event propagation. We are
// shipping the scaffold first so the gRPC surface is locked in.
package app

import (
	"context"

	pb "github.com/raihanpka/project-santara/services/sim-engine/internal/grpc_gen"
	"github.com/raihanpka/project-santara/services/sim-engine/internal/state"
)

// TickEngine runs simulation ticks against the state store.
type TickEngine struct {
	store *state.Store
}

// NewTickEngine wires the engine to its store.
func NewTickEngine(store *state.Store) *TickEngine {
	return &TickEngine{store: store}
}

// Run advances the simulation by n ticks. Paused simulations do not advance.
// Shocks are applied first if any, then the counter is incremented.
//
// ponytail: a real engine would do hunger, supply, demand, prices.
// v0.1.0 is the gRPC surface; the real work is gated on benchmarks
// proving the hot loop needs Go.
func (e *TickEngine) Run(ctx context.Context, simID string, n uint32) (*pb.WorldState, error) {
	sim, err := e.store.Get(simID)
	if err != nil {
		return nil, err
	}
	sim.Mu.Lock()
	defer sim.Mu.Unlock()
	if !sim.Paused {
		sim.Tick += uint64(n)
	}
	return sim.ToWorldStateLocked(), nil
}

// Pause marks the simulation paused.
func (e *TickEngine) Pause(ctx context.Context, simID string) error {
	sim, err := e.store.Get(simID)
	if err != nil {
		return err
	}
	sim.Mu.Lock()
	defer sim.Mu.Unlock()
	sim.Paused = true
	return nil
}

// Resume unmarks the simulation paused.
func (e *TickEngine) Resume(ctx context.Context, simID string) error {
	sim, err := e.store.Get(simID)
	if err != nil {
		return err
	}
	sim.Mu.Lock()
	defer sim.Mu.Unlock()
	sim.Paused = false
	return nil
}

// ApplyShock stores a shock effect on the simulation's macro indicators.
// v0.1.0 records the shock kind in the macro map. v0.2.0 will route to
// the right model (fiscal, political, climate, agrarian) and run a real
// pass-through.
func (e *TickEngine) ApplyShock(ctx context.Context, simID string, shock *pb.Shock) (*pb.WorldState, error) {
	sim, err := e.store.Get(simID)
	if err != nil {
		return nil, err
	}
	sim.Mu.Lock()
	defer sim.Mu.Unlock()
	switch shock.Kind.(type) {
	case *pb.Shock_Fiscal:
		if f := shock.GetFiscal(); f != nil {
			sim.Macro["pertamax_price_change_pct"] = f.PertamaxPriceChangePct
			sim.Macro["pertalite_price_change_pct"] = f.PertalitePriceChangePct
			sim.Macro["solar_price_change_pct"] = f.SolarPriceChangePct
			sim.Macro["bi_rate_change_bps"] = f.BiRateChangeBps
			sim.Macro["subsidi_change_pct"] = f.SubsidiChangePct
			sim.Macro["exchange_rate_shock_pct"] = f.ExchangeRateShockPct
		}
	case *pb.Shock_Political:
		if p := shock.GetPolitical(); p != nil {
			sim.Macro["cabinet_change_probability"] = p.CabinetChangeProbability
			sim.Macro["demo_intensity"] = p.DemoIntensity
		}
	case *pb.Shock_Climate:
		if c := shock.GetClimate(); c != nil {
			sim.Macro["el_nino_intensity"] = c.ElNinoIntensity
			sim.Macro["rainfall_change_pct"] = c.RainfallChangePct
		}
	case *pb.Shock_Agrarian:
		if a := shock.GetAgrarian(); a != nil {
			sim.Macro["tengkulak_share_change_pct"] = a.TengkulakShareChangePct
		}
	}
	return sim.ToWorldStateLocked(), nil
}
