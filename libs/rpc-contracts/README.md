# rpc-contracts

Protobuf contracts for cross-service communication in the Project Santara simulation platform. The contracts are the source of truth for the wire format. Generated stubs live in each consuming service.

## Status

Scaffold. The legacy contract at `libs/rpc-contracts/simulation.proto` (under the old monorepo) has been removed in this reset. A new contract will be defined in Phase 0 as part of the Go service scaffold.

## Planned Layout

```
rpc-contracts/
+-- proto/
|   +-- simulation.proto    gRPC contract between Python and Go
+-- README.md
```

## How Contracts Are Used

1. Edit `proto/simulation.proto` with the desired messages and services.
2. Generate Python stubs into the consuming Python service: `make proto-py`
3. Generate Go stubs into the consuming Go service: `make proto-go`
4. Both sides use the generated stubs as their SDK.

## Why a Separate Library

The contracts are shared between Python and Go. Keeping them in a separate library (not inside any one service) means:

- The contract is the single source of truth. No drift between Python and Go.
- Generated stubs live in the consuming service, not the contract library. This keeps the contract library small and version-pure.
- Breaking the contract is a major version bump of the contract library, with a written rationale.

## Planned Service Definitions

```protobuf
service InferenceService {
  rpc GetDecision(GetDecisionRequest) returns (GetDecisionResponse);
  rpc GetBatchDecisions(GetBatchDecisionsRequest) returns (GetBatchDecisionsResponse);
  rpc Tick(TickRequest) returns (TickResponse);
  rpc SpawnAgent(SpawnAgentRequest) returns (SpawnAgentResponse);
  rpc GetWorldSnapshot(GetWorldSnapshotRequest) returns (WorldSnapshot);
}
```

## Planned Messages

The exact message set is TBD and will be designed as part of Phase 0 Go service scaffold. The starting point is the legacy `simulation.proto` messages (AgentState, ActionDecision, WorldSnapshot), pruned to what the new architecture actually needs.

## Generation

Python (per consuming service):

```
python -m grpc_tools.protoc \
  --proto_path=../../libs/rpc-contracts/proto \
  --python_out=src/<service>/grpc_gen \
  --grpc_python_out=src/<service>/grpc_gen \
  simulation.proto
```

Go (per consuming service):

```
protoc \
  --proto_path=../../libs/rpc-contracts/proto \
  --go_out=internal/grpc_gen \
  --go_opt=paths=source_relative \
  --go-grpc_out=internal/grpc_gen \
  --go-grpc_opt=paths=source_relative \
  simulation.proto
```

## Versioning

The contract library follows its own semantic version. A breaking change to the contract is a major version bump of this library, separate from sim-kernel and separate from any service.
