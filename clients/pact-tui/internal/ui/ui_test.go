package ui

import (
	"context"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"

	"pacttui/internal/agent"
	"pacttui/internal/grant"
	"pacttui/internal/pact"
	"pacttui/internal/provider"
	"pacttui/internal/tools"
)

type stubProvider struct{}

func (stubProvider) Name() string                                  { return "claude" }
func (stubProvider) Model() string                                 { return "claude-test" }
func (stubProvider) Complete(context.Context, []any) (provider.Result, error) {
	return provider.Result{}, nil
}
func (stubProvider) AppendAssistant(*[]any, provider.Result)   {}
func (stubProvider) AppendToolResults(*[]any, []provider.ToolResult) {}
func (stubProvider) UserMessage(string) any                    { return nil }

// TestRender exercises the full view (layout, sidebar, decision card, header,
// footer) without a live terminal. Needs a backend for agent.Setup.
func TestRender(t *testing.T) {
	if os.Getenv("PACT_E2E") != "1" {
		t.Skip("set PACT_E2E=1 (with the backend running) to run the render test")
	}
	backend := os.Getenv("PACT_BACKEND")
	if backend == "" {
		backend = "http://localhost:8000"
	}
	ag := &agent.Agent{
		Client:        pact.NewClient(backend),
		Provider:      stubProvider{},
		Runner:        tools.NewRunner("."),
		Grant:         grant.Default(),
		Goal:          "render test",
		AgentID:       fmt.Sprintf("go-ui-%d", time.Now().UnixNano()),
		MaxToolRounds: 4,
	}
	if err := ag.Setup(context.Background()); err != nil {
		t.Fatalf("setup: %v", err)
	}

	var m tea.Model = New(ag, "http://localhost:5173")
	m, _ = m.Update(tea.WindowSizeMsg{Width: 120, Height: 40})
	m, _ = m.Update(setupDoneMsg{})
	m, _ = m.Update(eventMsg{ev: agent.AgentText{Text: "Here is the summary."}})
	m, _ = m.Update(eventMsg{ev: agent.ToolEvent{
		Tool: "web.read", Decision: "ALLOW", Risk: 0,
		Reasons: []string{"Action is valid and aligned with intent"}, ResultPreview: `{"status":"ok"}`,
	}})
	m, _ = m.Update(eventMsg{ev: agent.ToolEvent{
		Tool: "email.send", Decision: "BLOCK", Risk: 70,
		Reasons: []string{"Resource 'x@evil.com' is outside the authorized scope"},
	}})

	out := m.View()
	if snap := os.Getenv("PACT_SNAPSHOT"); snap != "" {
		_ = os.WriteFile(snap, []byte(out), 0o644)
	}
	for _, want := range []string{"PACT", "agent console", "web.read", "email.send", "AUTHORIZED TOOLS", "RESOURCE SCOPE"} {
		if !strings.Contains(out, want) {
			t.Errorf("rendered view missing %q", want)
		}
	}
	if len(out) < 200 {
		t.Errorf("rendered view too short:\n%s", out)
	}
}
