// Package telemetry wraps zerolog for sim-engine.
//
// ponytail: zerolog only, no zap, no slog. One logger per service.
package telemetry

import (
	"os"
	"strings"

	"github.com/rs/zerolog"
)

// New returns a configured zerolog.Logger writing JSON to stdout.
func New(level, service string) zerolog.Logger {
	lvl, err := zerolog.ParseLevel(strings.ToLower(level))
	if err != nil {
		lvl = zerolog.InfoLevel
	}
	return zerolog.New(os.Stdout).
		Level(lvl).
		With().
		Timestamp().
		Str("service", service).
		Logger()
}
