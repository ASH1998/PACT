# PACT agent TUI (Go + Bubble Tea)
#
# Go is expected on PATH. If you installed it locally (no sudo), add it first:
#   export PATH="$$HOME/.local/go/bin:$$PATH"

BINARY := pact-tui
PKG    := .

.PHONY: build run test vet tidy clean

build: ## Build the static binary into ./bin
	@mkdir -p bin
	go build -o bin/$(BINARY) $(PKG)
	@echo "built bin/$(BINARY)"

run: ## Run against a local backend (http://localhost:8000)
	go run $(PKG) $(ARGS)

test: ## Unit tests (crypto parity + canonical JSON). End-to-end tests skip
       ## unless PACT_E2E=1 and a backend is running.
	go test ./...

e2e: ## End-to-end tests against a running backend
	PACT_E2E=1 go test ./internal/agent ./internal/ui -v

vet:
	go vet ./...

tidy:
	go mod tidy

clean:
	rm -rf bin
