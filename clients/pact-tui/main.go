// Command pact-tui is a full-screen terminal UI for a PACT-protected agent.
// It is a real client of the PACT gateway over HTTP: it registers an agent,
// signs each Action Envelope locally (Ed25519), submits it for enforcement, and
// executes allowed tools on this machine — mirroring pact_chat.py with a proper
// TUI.
package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"pacttui/internal/agent"
	"pacttui/internal/grant"
	"pacttui/internal/pact"
	"pacttui/internal/provider"
	"pacttui/internal/tools"
	"pacttui/internal/ui"
)

func main() {
	providerName := flag.String("provider", "auto", "LLM provider: auto|claude|gemini|bedrock")
	model := flag.String("model", "", "Override CLAUDE_MODEL / GOOGLE_MODEL")
	goal := flag.String("goal", "Assist the user with web, email, file, summarization, and safe diagnostic tasks.", "Intent contract goal recorded in PACT")
	grantPath := flag.String("grant", "", "Path to an operator grant YAML (defaults to deny-by-default read-only)")
	backend := flag.String("backend", envOr("PACT_BACKEND_URL", "http://localhost:8000"), "PACT backend base URL")
	dashboard := flag.String("dashboard", envOr("PACT_DASHBOARD_URL", "http://localhost:5173"), "PACT dashboard base URL")
	agentID := flag.String("agent-id", "", "Stable agent id (default: random)")
	repoRoot := flag.String("repo-root", ".", "Repository root the file/shell tools operate within")
	maxRounds := flag.Int("max-tool-rounds", 4, "Max model<->tool rounds per turn")
	flag.Parse()

	root, err := filepath.Abs(*repoRoot)
	if err != nil {
		root = *repoRoot
	}
	// Load .env files (do not override already-set environment).
	loadEnv(filepath.Join(root, ".env"))
	loadEnv(filepath.Join(root, "backend", ".env"))

	prov, err := provider.Choose(*providerName, *model)
	if err != nil {
		fmt.Fprintln(os.Stderr, "provider error:", err)
		fmt.Fprintln(os.Stderr, "Set CLAUDE_API_KEY (claude), GOOGLE_API_KEY (gemini), or AWS creds (bedrock) in .env.")
		os.Exit(1)
	}

	client := pact.NewClient(*backend)
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	defer cancel()
	if err := client.Health(ctx); err != nil {
		fmt.Fprintf(os.Stderr, "PACT backend not reachable at %s\n", *backend)
		fmt.Fprintln(os.Stderr, "Start it:  cd backend && uvicorn app.main:app --reload --port 8000")
		os.Exit(1)
	}

	g := grant.Default()
	if *grantPath != "" {
		loaded, err := grant.Load(*grantPath)
		if err != nil {
			fmt.Fprintln(os.Stderr, "grant error:", err)
			os.Exit(1)
		}
		g = loaded
	}

	id := *agentID
	if id == "" {
		id = "pact-cli-" + randHex(8)
	}

	ag := &agent.Agent{
		Client:        client,
		Provider:      prov,
		Runner:        tools.NewRunner(root),
		Grant:         g,
		Goal:          *goal,
		AgentID:       id,
		MaxToolRounds: *maxRounds,
	}

	p := tea.NewProgram(ui.New(ag, *dashboard), tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func randHex(n int) string {
	b := make([]byte, (n+1)/2)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)[:n]
}

// loadEnv reads KEY=VALUE lines from path and sets any not already in the
// environment (mirrors python-dotenv load with override=False).
func loadEnv(path string) {
	f, err := os.Open(path)
	if err != nil {
		return
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		line = strings.TrimPrefix(line, "export ")
		eq := strings.IndexByte(line, '=')
		if eq < 0 {
			continue
		}
		key := strings.TrimSpace(line[:eq])
		val := strings.TrimSpace(line[eq+1:])
		val = strings.Trim(val, `"'`)
		if key != "" && os.Getenv(key) == "" {
			_ = os.Setenv(key, val)
		}
	}
}
