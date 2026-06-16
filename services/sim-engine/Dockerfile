FROM golang:1.22-alpine AS builder

WORKDIR /src
COPY services/sim-engine/go.mod services/sim-engine/go.sum ./
RUN go mod download
COPY services/sim-engine/ ./
RUN CGO_ENABLED=0 go build -ldflags="-s -w" -o /out/sim-engine-server ./cmd/server

FROM alpine:3.20
RUN apk add --no-cache ca-certificates
COPY --from=builder /out/sim-engine-server /usr/local/bin/sim-engine-server
EXPOSE 50052
ENTRYPOINT ["/usr/local/bin/sim-engine-server"]
