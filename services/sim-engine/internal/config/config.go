// Package config loads runtime configuration from environment variables.
//
// ponytail: env-only, no flags. Single binary, single config surface.
package config

import (
	"os"
	"strconv"
)

// Config holds the runtime knobs for sim-engine.
type Config struct {
	GRPCAddr    string // ":50052"
	LogLevel    string // "info" | "debug" | "warn" | "error"
	MaxSims     int    // 1024 default
	MaxAgents   int    // 1_000_000 default
	ServiceName string // "sim-engine"
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getenvInt(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return fallback
}

// Load reads the config from the process environment.
func Load() Config {
	return Config{
		GRPCAddr:    getenv("SIM_ENGINE_GRPC_ADDR", ":50052"),
		LogLevel:    getenv("SIM_ENGINE_LOG_LEVEL", "info"),
		MaxSims:     getenvInt("SIM_ENGINE_MAX_SIMS", 1024),
		MaxAgents:   getenvInt("SIM_ENGINE_MAX_AGENTS", 1_000_000),
		ServiceName: getenv("SIM_ENGINE_SERVICE_NAME", "sim-engine"),
	}
}
