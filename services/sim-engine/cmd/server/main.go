// Command sim-engine-server is the entry point for the Go tick engine.
//
// ponytail: gRPC only, no HTTP. The Python gateway talks to this server
// over the protobuf contract in libs/rpc-contracts/proto/simulation.proto.
package main

import (
	"errors"
	"net"
	"os"
	"os/signal"
	"syscall"

	"github.com/rs/zerolog"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"

	"github.com/raihanpka/sim-engine/internal/app"
	"github.com/raihanpka/sim-engine/internal/config"
	grpcserver "github.com/raihanpka/sim-engine/internal/grpc"
	pb "github.com/raihanpka/sim-engine/internal/grpc_gen"
	"github.com/raihanpka/sim-engine/internal/state"

	_ "github.com/raihanpka/sim-engine/internal/telemetry"
)

func main() {
	cfg := config.Load()
	log := zerolog.New(os.Stdout).
		Level(zerolog.InfoLevel).
		With().
		Timestamp().
		Str("service", cfg.ServiceName).
		Logger()

	store := state.NewStore(cfg.MaxSims, cfg.MaxAgents)
	engine := app.NewTickEngine(store)
	srv := grpcserver.New(store, engine, log)

	lis, err := net.Listen("tcp", cfg.GRPCAddr)
	if err != nil {
		log.Fatal().Err(err).Str("addr", cfg.GRPCAddr).Msg("listen failed")
	}

	g := grpc.NewServer()
	pb.RegisterSimulationServiceServer(g, srv)
	reflection.Register(g)

	go func() {
		log.Info().Str("addr", cfg.GRPCAddr).Msg("sim-engine listening")
		if err := g.Serve(lis); err != nil && !errors.Is(err, grpc.ErrServerStopped) {
			log.Fatal().Err(err).Msg("gRPC serve failed")
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop
	log.Info().Msg("shutting down sim-engine")
	g.GracefulStop()
}
