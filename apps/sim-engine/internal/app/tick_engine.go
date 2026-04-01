// Package app contains the application orchestration layer.
// This file implements the tick engine that drives the simulation.
package app

import (
	"context"
	"sync"
	"sync/atomic"
	"time"

	"github.com/rs/zerolog"

	"github.com/santara/sim-engine/internal/app/commands"
	"github.com/santara/sim-engine/internal/app/queries"
	"github.com/santara/sim-engine/internal/domain"
)

// TickEngineConfig holds configuration for the tick engine.
type TickEngineConfig struct {
	TickRateMs            int     // Target tick duration in milliseconds
	MaxConcurrentThinking int     // Maximum agents in THINKING state
	HungerRate            float64 // Hunger increase per tick
	HealthDecayRate       float64 // Health decay when hungry
	AutoStart             bool    // Start ticking immediately
}

// DefaultTickEngineConfig returns default configuration.
func DefaultTickEngineConfig() TickEngineConfig {
	return TickEngineConfig{
		TickRateMs:            50, // 20 ticks per second
		MaxConcurrentThinking: 10,
		HungerRate:            0.1,
		HealthDecayRate:       0.5,
		AutoStart:             false,
	}
}

// TickEngine manages the simulation tick loop.
// It implements the "Tick" phase of the Tick-to-Think loop.
type TickEngine struct {
	config TickEngineConfig
	logger zerolog.Logger

	// Handlers
	processTickHandler   *commands.ProcessTickHandler
	getWorldStateHandler *queries.GetWorldStateHandler

	// State
	currentTick atomic.Int64
	running     atomic.Bool
	paused      atomic.Bool

	// Control channels
	stopCh  chan struct{}
	pauseCh chan struct{}

	// Synchronization
	mu sync.RWMutex
	wg sync.WaitGroup

	// Listeners for tick events
	tickListeners []func(tick int64, result *commands.ProcessTickResult)
}

// NewTickEngine creates a new tick engine.
func NewTickEngine(
	config TickEngineConfig,
	processTickHandler *commands.ProcessTickHandler,
	getWorldStateHandler *queries.GetWorldStateHandler,
	logger zerolog.Logger,
) *TickEngine {
	return &TickEngine{
		config:               config,
		logger:               logger,
		processTickHandler:   processTickHandler,
		getWorldStateHandler: getWorldStateHandler,
		stopCh:               make(chan struct{}),
		pauseCh:              make(chan struct{}),
		tickListeners:        make([]func(int64, *commands.ProcessTickResult), 0),
	}
}

// Start begins the tick loop.
func (e *TickEngine) Start(ctx context.Context) error {
	if e.running.Load() {
		return nil // Already running
	}

	e.running.Store(true)
	e.stopCh = make(chan struct{})

	e.wg.Add(1)
	go e.runTickLoop(ctx)

	e.logger.Info().
		Int("tick_rate_ms", e.config.TickRateMs).
		Int("max_concurrent_thinking", e.config.MaxConcurrentThinking).
		Msg("tick engine started")

	return nil
}

// Stop halts the tick loop.
func (e *TickEngine) Stop() {
	if !e.running.Load() {
		return
	}

	e.running.Store(false)
	close(e.stopCh)
	e.wg.Wait()

	e.logger.Info().
		Int64("final_tick", e.currentTick.Load()).
		Msg("tick engine stopped")
}

// Pause temporarily pauses the tick loop.
func (e *TickEngine) Pause() {
	e.paused.Store(true)
	e.logger.Info().Int64("tick", e.currentTick.Load()).Msg("tick engine paused")
}

// Resume continues a paused tick loop.
func (e *TickEngine) Resume() {
	e.paused.Store(false)
	e.logger.Info().Int64("tick", e.currentTick.Load()).Msg("tick engine resumed")
}

// IsRunning returns true if the engine is running.
func (e *TickEngine) IsRunning() bool {
	return e.running.Load()
}

// IsPaused returns true if the engine is paused.
func (e *TickEngine) IsPaused() bool {
	return e.paused.Load()
}

// CurrentTick returns the current tick number.
func (e *TickEngine) CurrentTick() int64 {
	return e.currentTick.Load()
}

// ProcessSingleTick manually processes one tick (for testing/debugging).
func (e *TickEngine) ProcessSingleTick(ctx context.Context) (*commands.ProcessTickResult, error) {
	tick := e.currentTick.Add(1)

	cmd := commands.ProcessTickCommand{
		TickNumber:      tick,
		HungerRate:      e.config.HungerRate,
		HealthDecayRate: e.config.HealthDecayRate,
	}

	result, err := e.processTickHandler.Handle(ctx, cmd)
	if err != nil {
		return nil, err
	}

	e.notifyListeners(tick, result)
	return result, nil
}

// GetWorldState returns the current world state.
func (e *TickEngine) GetWorldState(ctx context.Context, includeEntities bool) (*queries.WorldSnapshot, error) {
	query := queries.GetWorldStateQuery{
		IncludeEntities: includeEntities,
		CurrentTick:     e.currentTick.Load(),
	}
	return e.getWorldStateHandler.Handle(ctx, query)
}

// OnTick registers a listener for tick events.
func (e *TickEngine) OnTick(listener func(tick int64, result *commands.ProcessTickResult)) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.tickListeners = append(e.tickListeners, listener)
}

// runTickLoop is the main tick loop goroutine.
func (e *TickEngine) runTickLoop(ctx context.Context) {
	defer e.wg.Done()

	ticker := time.NewTicker(time.Duration(e.config.TickRateMs) * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-e.stopCh:
			return
		case <-ticker.C:
			if e.paused.Load() {
				continue
			}

			tick := e.currentTick.Add(1)

			cmd := commands.ProcessTickCommand{
				TickNumber:      tick,
				HungerRate:      e.config.HungerRate,
				HealthDecayRate: e.config.HealthDecayRate,
			}

			result, err := e.processTickHandler.Handle(ctx, cmd)
			if err != nil {
				e.logger.Error().Err(err).Int64("tick", tick).Msg("tick processing failed")
				continue
			}

			// Warn if tick took too long
			if result.DurationMs > int64(e.config.TickRateMs) {
				e.logger.Warn().
					Int64("tick", tick).
					Int64("duration_ms", result.DurationMs).
					Int("target_ms", e.config.TickRateMs).
					Msg("tick exceeded target duration")
			}

			e.notifyListeners(tick, result)
		}
	}
}

// notifyListeners calls all registered tick listeners.
func (e *TickEngine) notifyListeners(tick int64, result *commands.ProcessTickResult) {
	e.mu.RLock()
	listeners := make([]func(int64, *commands.ProcessTickResult), len(e.tickListeners))
	copy(listeners, e.tickListeners)
	e.mu.RUnlock()

	for _, listener := range listeners {
		listener(tick, result)
	}
}

// WorkerPool manages a pool of goroutines for parallel agent processing.
type WorkerPool struct {
	workers    int
	jobQueue   chan func()
	workerWg   sync.WaitGroup
	shutdownCh chan struct{}
	running    atomic.Bool
	logger     zerolog.Logger
}

// NewWorkerPool creates a new worker pool.
func NewWorkerPool(workers int, queueSize int, logger zerolog.Logger) *WorkerPool {
	return &WorkerPool{
		workers:    workers,
		jobQueue:   make(chan func(), queueSize),
		shutdownCh: make(chan struct{}),
		logger:     logger,
	}
}

// Start initializes and starts the worker goroutines.
func (p *WorkerPool) Start() {
	if p.running.Load() {
		return
	}

	p.running.Store(true)
	p.shutdownCh = make(chan struct{})

	for i := 0; i < p.workers; i++ {
		p.workerWg.Add(1)
		go p.worker(i)
	}

	p.logger.Info().Int("workers", p.workers).Msg("worker pool started")
}

// Stop shuts down the worker pool.
func (p *WorkerPool) Stop() {
	if !p.running.Load() {
		return
	}

	p.running.Store(false)
	close(p.shutdownCh)
	p.workerWg.Wait()

	p.logger.Info().Msg("worker pool stopped")
}

// Submit adds a job to the queue.
func (p *WorkerPool) Submit(job func()) bool {
	if !p.running.Load() {
		return false
	}

	select {
	case p.jobQueue <- job:
		return true
	default:
		// Queue is full
		p.logger.Warn().Msg("worker pool queue full, job dropped")
		return false
	}
}

// SubmitWait adds a job and waits for it to complete.
func (p *WorkerPool) SubmitWait(job func()) bool {
	done := make(chan struct{})
	wrapped := func() {
		defer close(done)
		job()
	}

	if !p.Submit(wrapped) {
		return false
	}

	<-done
	return true
}

// worker is the main loop for a worker goroutine.
func (p *WorkerPool) worker(id int) {
	defer p.workerWg.Done()

	for {
		select {
		case <-p.shutdownCh:
			return
		case job := <-p.jobQueue:
			if job != nil {
				func() {
					defer func() {
						if r := recover(); r != nil {
							p.logger.Error().
								Int("worker_id", id).
								Interface("panic", r).
								Msg("worker panic recovered")
						}
					}()
					job()
				}()
			}
		}
	}
}

// ProcessAgentsConcurrently processes multiple agents in parallel.
func (p *WorkerPool) ProcessAgentsConcurrently(
	ctx context.Context,
	agents []*domain.Agent,
	processor func(ctx context.Context, agent *domain.Agent) error,
) []error {
	if len(agents) == 0 {
		return nil
	}

	errors := make([]error, len(agents))
	var wg sync.WaitGroup

	for i, agent := range agents {
		wg.Add(1)
		idx := i
		a := agent

		p.Submit(func() {
			defer wg.Done()
			select {
			case <-ctx.Done():
				errors[idx] = ctx.Err()
			default:
				errors[idx] = processor(ctx, a)
			}
		})
	}

	wg.Wait()
	return errors
}

// QueueLength returns the current number of jobs waiting.
func (p *WorkerPool) QueueLength() int {
	return len(p.jobQueue)
}
