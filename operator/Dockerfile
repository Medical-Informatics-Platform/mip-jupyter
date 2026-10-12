# Base images are pinned by digest; bump the digest to pick up base fixes.
FROM golang:1.26@sha256:d7722066f0b60ceccb6c0643cbed1f5f9e15506ac237146c95333504d7805d89 AS builder
ARG TARGETOS
ARG TARGETARCH
WORKDIR /workspace
# Dependencies first, so source changes reuse the module download layer.
COPY go.mod go.sum ./
RUN go mod download
COPY cmd/main.go cmd/main.go
COPY api/ api/
COPY internal/ internal/
RUN CGO_ENABLED=0 GOOS=${TARGETOS:-linux} GOARCH=${TARGETARCH} go build -a -o manager cmd/main.go

FROM gcr.io/distroless/static:nonroot@sha256:e2e927ec666bae08560abb3c55d0659eceabb657f56b6782ab500a9fc7f555e3
WORKDIR /
COPY --from=builder /workspace/manager .
USER 65532:65532
ENTRYPOINT ["/manager"]
