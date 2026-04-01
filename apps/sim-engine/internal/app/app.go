// Package app provides the application layer coordinating use cases.
// This file sets up dependency injection for the simulation engine.
package app

import (
	"os"

	"github.com/rs/zerolog"

	"github.com/santara/sim-engine/internal/app/commands"
	"github.com/santara/sim-engine/internal/app/queries"
	"github.com/santara/sim-engine/internal/domain"
)

// Application is the central coordinator providing access to all handlers.
// This implements the CQRS-Lite pattern from ThreeDotsLabs.
type Application struct {
	// Commands (write operations)
	Commands Commands

	// Queries (read operations)
	Queries Queries

	// Infrastructure
	TickEngine *TickEngine
	WorkerPool *WorkerPool
}

// Commands holds all command handlers.
type Commands struct {
	ProcessTick *commands.ProcessTickHandler
	SpawnAgent  *commands.SpawnAgentHandler
}

// Queries holds all query handlers.
type Queries struct {
	GetWorldState   *queries.GetWorldStateHandler
	GetAgent        *queries.GetAgentHandler
	GetNearbyMarkets *queries.GetNearbyMarketsHandler
}

// ApplicationConfig holds configuration for the application.
type ApplicationConfig struct {
	TickEngine TickEngineConfig
	WorkerPool WorkerPoolConfig
	LogLevel   string
	LogFormat  string // "json" or "console"
}

// WorkerPoolConfig holds configuration for the worker pool.
type WorkerPoolConfig struct {
	Workers   int
	QueueSize int
}

// DefaultApplicationConfig returns default configuration.
func DefaultApplicationConfig() ApplicationConfig {
	return ApplicationConfig{
		TickEngine: DefaultTickEngineConfig(),
		WorkerPool: WorkerPoolConfig{
			Workers:   4,
			QueueSize: 1000,
		},
		LogLevel:  "info",
		LogFormat: "json",
	}
}

// Dependencies holds all external dependencies for the application.
type Dependencies struct {
	AgentRepo       domain.AgentRepository
	MarketRepo      domain.MarketRepository
	RegionRepo      domain.RegionRepository
	InferenceClient domain.InferenceClient
}

// NewApplication creates a new Application with all handlers wired up.
func NewApplication(deps Dependencies, config ApplicationConfig) *Application {
	// Setup logger
	logger := setupLogger(config)

	// Create command handlers
	processTickHandler := commands.NewProcessTickHandler(
		deps.AgentRepo,
		deps.MarketRepo,
		deps.InferenceClient,
		logger,
		config.TickEngine.MaxConcurrentThinking,
	)

	spawnAgentHandler := commands.NewSpawnAgentHandler(
		deps.AgentRepo,
		logger,
	)

	// Create query handlers
	getWorldStateHandler := queries.NewGetWorldStateHandler(
		deps.AgentRepo,
		deps.MarketRepo,
		deps.RegionRepo,
		logger,
	)

	getAgentHandler := queries.NewGetAgentHandler(
		deps.AgentRepo,
		logger,
	)

	getNearbyMarketsHandler := queries.NewGetNearbyMarketsHandler(
		deps.MarketRepo,
		logger,
	)

	// Create tick engine
	tickEngine := NewTickEngine(
		config.TickEngine,
		processTickHandler,
		getWorldStateHandler,
		logger,
	)

	// Create worker pool
	workerPool := NewWorkerPool(
		config.WorkerPool.Workers,
		config.WorkerPool.QueueSize,
		logger,
	)

	return &Application{
		Commands: Commands{
			ProcessTick: processTickHandler,
			SpawnAgent:  spawnAgentHandler,
		},
		Queries: Queries{
			GetWorldState:   getWorldStateHandler,
			GetAgent:        getAgentHandler,
			GetNearbyMarkets: getNearbyMarketsHandler,
		},
		TickEngine: tickEngine,
		WorkerPool: workerPool,
	}
}

// setupLogger creates and configures the logger.
func setupLogger(config ApplicationConfig) zerolog.Logger {
	var logger zerolog.Logger

	if config.LogFormat == "console" {
		logger = zerolog.New(zerolog.ConsoleWriter{Out: os.Stdout}).
			With().
			Timestamp().
			Caller().
			Logger()
	} else {
		logger = zerolog.New(os.Stdout).
			With().
			Timestamp().
			Caller().
			Logger()
	}

	// Set log level
	switch config.LogLevel {
	case "debug":
		zerolog.SetGlobalLevel(zerolog.DebugLevel)
	case "info":
		zerolog.SetGlobalLevel(zerolog.InfoLevel)
	case "warn":
		zerolog.SetGlobalLevel(zerolog.WarnLevel)
	case "error":
		zerolog.SetGlobalLevel(zerolog.ErrorLevel)
	default:
		zerolog.SetGlobalLevel(zerolog.InfoLevel)
	}

	return logger
}
