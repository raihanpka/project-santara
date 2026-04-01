// Package main is the entry point for the Santara Simulation Engine.
package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"github.com/caarlos0/env/v11"
	"github.com/google/uuid"
	"github.com/rs/zerolog"

	"github.com/santara/sim-engine/internal/adapters/inference"
	"github.com/santara/sim-engine/internal/adapters/state"
	"github.com/santara/sim-engine/internal/app"
	"github.com/santara/sim-engine/internal/app/commands"
	"github.com/santara/sim-engine/internal/domain"
)

// Config holds application configuration from environment variables.
type Config struct {
	// Server configuration
	GRPCPort int    `env:"GRPC_PORT" envDefault:"50052"`
	HTTPPort int    `env:"HTTP_PORT" envDefault:"8080"`
	LogLevel string `env:"LOG_LEVEL" envDefault:"info"`
	LogFormat string `env:"LOG_FORMAT" envDefault:"json"`

	// Inference service
	InferenceAddress string `env:"INFERENCE_ADDRESS" envDefault:"localhost:50051"`

	// Simulation configuration
	TickRateMs            int     `env:"TICK_RATE_MS" envDefault:"50"`
	MaxConcurrentThinking int     `env:"MAX_CONCURRENT_THINKING" envDefault:"10"`
	HungerRate            float64 `env:"HUNGER_RATE" envDefault:"0.1"`
	HealthDecayRate       float64 `env:"HEALTH_DECAY_RATE" envDefault:"0.5"`
	AutoStart             bool    `env:"AUTO_START" envDefault:"false"`

	// Worker pool
	WorkerPoolSize  int `env:"WORKER_POOL_SIZE" envDefault:"4"`
	WorkerQueueSize int `env:"WORKER_QUEUE_SIZE" envDefault:"1000"`
}

func main() {
	// Parse configuration
	cfg := Config{}
	if err := env.Parse(&cfg); err != nil {
		panic(err)
	}

	// Setup logger
	var logger zerolog.Logger
	if cfg.LogFormat == "console" {
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
	switch cfg.LogLevel {
	case "debug":
		zerolog.SetGlobalLevel(zerolog.DebugLevel)
	case "info":
		zerolog.SetGlobalLevel(zerolog.InfoLevel)
	case "warn":
		zerolog.SetGlobalLevel(zerolog.WarnLevel)
	case "error":
		zerolog.SetGlobalLevel(zerolog.ErrorLevel)
	}

	logger.Info().
		Int("grpc_port", cfg.GRPCPort).
		Int("http_port", cfg.HTTPPort).
		Str("inference_address", cfg.InferenceAddress).
		Int("tick_rate_ms", cfg.TickRateMs).
		Msg("starting simulation engine")

	// Create repositories
	agentRepo := state.NewInMemoryAgentRepository()
	marketRepo := state.NewInMemoryMarketRepository()
	regionRepo := state.NewInMemoryRegionRepository()

	// Create inference client
	inferenceClient, err := inference.NewGRPCInferenceClient(
		inference.ClientConfig{
			Address: cfg.InferenceAddress,
		},
		logger,
	)
	if err != nil {
		logger.Warn().Err(err).Msg("failed to create inference client, using mock")
		inferenceClient = nil
	}

	// Use mock if real client failed
	var infClient domain.InferenceClient
	if inferenceClient != nil {
		infClient = inferenceClient
	} else {
		infClient = inference.NewMockInferenceClient()
	}

	// Create application
	appConfig := app.ApplicationConfig{
		TickEngine: app.TickEngineConfig{
			TickRateMs:            cfg.TickRateMs,
			MaxConcurrentThinking: cfg.MaxConcurrentThinking,
			HungerRate:            cfg.HungerRate,
			HealthDecayRate:       cfg.HealthDecayRate,
			AutoStart:             cfg.AutoStart,
		},
		WorkerPool: app.WorkerPoolConfig{
			Workers:   cfg.WorkerPoolSize,
			QueueSize: cfg.WorkerQueueSize,
		},
		LogLevel:  cfg.LogLevel,
		LogFormat: cfg.LogFormat,
	}

	application := app.NewApplication(
		app.Dependencies{
			AgentRepo:       agentRepo,
			MarketRepo:      marketRepo,
			RegionRepo:      regionRepo,
			InferenceClient: infClient,
		},
		appConfig,
	)

	// Seed some initial data for testing
	seedTestData(context.Background(), agentRepo, marketRepo, regionRepo, logger)

	// Start worker pool
	application.WorkerPool.Start()
	defer application.WorkerPool.Stop()

	// Setup graceful shutdown
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	// Start tick engine if auto-start is enabled
	if cfg.AutoStart {
		if err := application.TickEngine.Start(ctx); err != nil {
			logger.Error().Err(err).Msg("failed to start tick engine")
		}
	}

	// Log tick events
	application.TickEngine.OnTick(func(tick int64, result *commands.ProcessTickResult) {
		if tick%100 == 0 { // Log every 100 ticks
			logger.Info().
				Int64("tick", tick).
				Int("agents_processed", result.AgentsProcessed).
				Int("decisions_needed", result.DecisionsNeeded).
				Int64("duration_ms", result.DurationMs).
				Msg("simulation progress")
		}
	})

	logger.Info().Msg("simulation engine ready")

	// TODO: Start gRPC server for SimulationService
	// TODO: Start HTTP server for REST API / health checks

	// Wait for shutdown signal
	<-sigCh
	logger.Info().Msg("shutdown signal received")

	// Stop tick engine
	application.TickEngine.Stop()

	// Close inference client
	if inferenceClient != nil {
		inferenceClient.Close()
	}

	logger.Info().Msg("simulation engine stopped")
}

// seedTestData creates some initial test data.
func seedTestData(
	ctx context.Context,
	agentRepo domain.AgentRepository,
	marketRepo domain.MarketRepository,
	regionRepo domain.RegionRepository,
	logger zerolog.Logger,
) {
	// Create a test region
	region := domain.NewRegion(
		"Kabupaten Bandung",
		"32.04",
		2,
		domain.Coordinates{
			Latitude:  -6.9175,
			Longitude: 107.6191,
		},
	)
	region.Population = 3500000
	region.AreaKm2 = 1767.96

	if err := regionRepo.Save(ctx, region); err != nil {
		logger.Error().Err(err).Msg("failed to create test region")
		return
	}

	// Create a test market
	market := domain.NewMarket(
		"Pasar Induk Caringin",
		region.ID,
		domain.MarketTypeRegional,
		domain.Coordinates{
			Latitude:  -6.9211,
			Longitude: 107.5973,
		},
	)
	market.SetPrices(domain.PriceList{
		domain.CropTypeRice:      12000,
		domain.CropTypeCorn:      5000,
		domain.CropTypeCassava:   3000,
		domain.CropTypeSoybean:   10000,
		domain.CropTypeVegetable: 8000,
	})
	market.AddSupply(domain.CropTypeRice, 1000)
	market.AddSupply(domain.CropTypeCorn, 500)

	if err := marketRepo.Save(ctx, market); err != nil {
		logger.Error().Err(err).Msg("failed to create test market")
		return
	}

	// Create some test agents
	for i := 0; i < 10; i++ {
		agent := domain.NewAgent(
			"Petani "+uuid.NewString()[:8],
			region.ID,
			domain.Coordinates{
				Latitude:  -6.9 + float64(i)*0.01,
				Longitude: 107.6 + float64(i)*0.01,
			},
		)
		agent.Cash = 500000
		agent.AddInventory(domain.CropTypeRice, 50)
		agent.AddInventory(domain.CropTypeCorn, 30)

		if err := agentRepo.Save(ctx, agent); err != nil {
			logger.Error().Err(err).Msg("failed to create test agent")
		}
	}

	agentCount, _ := agentRepo.Count(ctx)
	marketCount, _ := marketRepo.Count(ctx)
	regionCount, _ := regionRepo.Count(ctx)

	logger.Info().
		Int("agents", agentCount).
		Int("markets", marketCount).
		Int("regions", regionCount).
		Msg("test data seeded")
}
