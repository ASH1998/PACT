// Package agent orchestrates a PACT-protected chat turn: it drives the LLM
// provider, signs and submits each tool call to the gateway, executes allowed
// tools locally, and streams events to the UI. It mirrors PactChatAgent from
// pact_chat.py but over the HTTP gateway.
package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"pacttui/internal/grant"
	"pacttui/internal/pact"
	"pacttui/internal/provider"
	"pacttui/internal/tools"
)

// Event is streamed to the UI as a turn progresses.
type Event interface{}

// AgentText is assistant prose.
type AgentText struct{ Text string }

// ToolEvent is a PACT decision for one tool call.
type ToolEvent struct {
	Tool          string
	Decision      string
	Risk          int
	Severity      string
	Reasons       []string
	ResultPreview string
	Approved      bool
}

// ApprovalNeeded signals the turn paused awaiting human approval.
type ApprovalNeeded struct {
	Tools   []string
	Risk    int
	Reasons []string
}

// Done marks the end of a turn (no more tool calls).
type Done struct{}

// Err carries a fatal turn error.
type Err struct{ Error error }

type pendingCall struct {
	providerToolName string
	toolCallID       string
	args             map[string]any
}

// Agent holds the session state for a PACT-protected chat.
type Agent struct {
	Client   *pact.Client
	Provider provider.Provider
	Runner   *tools.Runner
	Grant    grant.Grant
	Goal     string
	AgentID  string

	MaxToolRounds int

	privKey       string
	intentHash    string
	runID         string
	allowedTools  []string
	forbidden     []string
	resourceScope map[string][]string

	messages   []any
	stepID     int
	parentHash string // "" => send JSON null (first action)

	pending      []pendingCall
	roundResults []provider.ToolResult
	rounds       int
}

// RunID returns the active run id.
func (a *Agent) RunID() string { return a.runID }

// AllowedTools returns the tools authorized by the grant for this session.
func (a *Agent) AllowedTools() []string { return a.allowedTools }

// Forbidden returns the tools blocked by the grant ceiling.
func (a *Agent) Forbidden() []string { return a.forbidden }

// ResourceScope returns the operator resource scope.
func (a *Agent) ResourceScope() map[string][]string { return a.resourceScope }

// HasPending reports whether the turn is paused on approval.
func (a *Agent) HasPending() bool { return len(a.pending) > 0 }

// Setup registers the agent, tools, intent, and run.
func (a *Agent) Setup(ctx context.Context) error {
	if a.MaxToolRounds == 0 {
		a.MaxToolRounds = 4
	}
	priv, err := a.Client.RegisterAgent(ctx, a.AgentID, "local-cli", a.Provider.Name()+"_chat_agent", tools.AllowedToolIDs)
	if err != nil {
		return fmt.Errorf("register agent: %w", err)
	}
	a.privKey = priv

	for _, id := range tools.AllowedToolIDs {
		m := tools.Metadata[id]
		if err := a.Client.RegisterTool(ctx, pact.ToolMeta{
			ToolID: id, Name: m.DisplayName, Description: m.Description,
			SideEffect: m.SideEffect, Sensitivity: m.Sensitivity,
			ResourceType: m.ResourceType, RequiresApproval: m.RequiresApproval,
		}); err != nil {
			return fmt.Errorf("register tool %s: %w", id, err)
		}
	}

	a.allowedTools = a.Grant.ToolCeiling(tools.AllowedToolIDs)
	allowedSet := map[string]bool{}
	for _, t := range a.allowedTools {
		allowedSet[t] = true
	}
	a.forbidden = nil
	for _, t := range tools.AllowedToolIDs {
		if !allowedSet[t] {
			a.forbidden = append(a.forbidden, t)
		}
	}
	a.resourceScope = a.Grant.ResourceScope

	ih, err := a.Client.CreateIntent(ctx, a.Goal, a.AgentID, a.allowedTools, a.forbidden, a.resourceScope)
	if err != nil {
		return fmt.Errorf("create intent: %w", err)
	}
	a.intentHash = ih

	rid, err := a.Client.CreateRun(ctx, a.AgentID, "interactive_cli", a.Goal)
	if err != nil {
		return fmt.Errorf("create run: %w", err)
	}
	a.runID = rid
	return nil
}

// VerifyLedger returns the ledger verification for this run.
func (a *Agent) VerifyLedger(ctx context.Context) (pact.Ledger, error) {
	return a.Client.VerifyLedger(ctx, a.runID)
}

// Complete marks the run completed.
func (a *Agent) Complete(ctx context.Context) error { return a.Client.CompleteRun(ctx, a.runID) }

// Turn runs a full model/tool loop for a user message, emitting events. If a
// tool requires approval the turn pauses (HasPending becomes true) and returns;
// the caller invokes Resume after collecting the human decision.
func (a *Agent) Turn(ctx context.Context, userText string, emit func(Event)) {
	a.messages = append(a.messages, a.Provider.UserMessage(userText))
	a.rounds = 0
	a.loop(ctx, userText, emit)
}

// Resume continues a paused turn after a human approves or denies.
func (a *Agent) Resume(ctx context.Context, approve bool, emit func(Event)) {
	pending := a.pending
	a.pending = nil
	combined := a.roundResults
	a.roundResults = nil

	for _, p := range pending {
		if approve {
			tr := a.execTool(ctx, p.providerToolName, p.toolCallID, p.args, true, emit)
			combined = append(combined, tr)
		} else {
			content := map[string]any{
				"tool":     tools.NameToID[p.providerToolName],
				"decision": "BLOCK",
				"reasons":  []string{"Human denied the pending approval in the CLI."},
				"result":   nil,
			}
			emit(ToolEvent{Tool: tools.NameToID[p.providerToolName], Decision: "BLOCK",
				Reasons: []string{"Human denied the pending approval"}, Approved: false})
			combined = append(combined, provider.ToolResult{
				ProviderToolName: p.providerToolName, ToolCallID: p.toolCallID, Content: content,
			})
		}
	}
	a.Provider.AppendToolResults(&a.messages, combined)
	a.rounds++
	a.loop(ctx, "[approval resolved]", emit)
}

func (a *Agent) loop(ctx context.Context, userText string, emit func(Event)) {
	for {
		result, err := a.Provider.Complete(ctx, a.messages)
		if err != nil {
			emit(Err{Error: err})
			return
		}
		a.recordModelEvent(ctx, userText, result)
		if result.Text != "" {
			emit(AgentText{Text: result.Text})
		}
		a.Provider.AppendAssistant(&a.messages, result)

		if len(result.ToolCalls) == 0 {
			emit(Done{})
			return
		}
		if a.rounds >= a.MaxToolRounds {
			emit(AgentText{Text: "PACT stopped tool loop: max tool rounds reached."})
			emit(Done{})
			return
		}

		var allowedResults []provider.ToolResult
		for _, call := range result.ToolCalls {
			toolID := tools.NameToID[call.ProviderToolName]
			// Probe the decision first; route REQUIRE_APPROVAL to pending.
			tr, decision := a.execToolDecide(ctx, call, false, emit)
			if decision == "REQUIRE_APPROVAL" {
				a.pending = append(a.pending, pendingCall{call.ProviderToolName, call.ToolCallID, call.Args})
				continue
			}
			_ = toolID
			allowedResults = append(allowedResults, tr)
		}

		if len(a.pending) > 0 {
			a.roundResults = allowedResults
			var ptools []string
			for _, p := range a.pending {
				ptools = append(ptools, tools.NameToID[p.providerToolName])
			}
			emit(ApprovalNeeded{Tools: ptools})
			return
		}

		a.Provider.AppendToolResults(&a.messages, allowedResults)
		a.rounds++
	}
}

// execToolDecide submits the tool call to the gateway and, for ALLOW, executes
// it locally and attaches the result. Returns the tool result and the decision.
func (a *Agent) execToolDecide(ctx context.Context, call provider.ToolCall, approved bool, emit func(Event)) (provider.ToolResult, string) {
	toolID, ok := tools.NameToID[call.ProviderToolName]
	if !ok {
		content := map[string]any{
			"decision": "BLOCK",
			"reasons":  []string{"Unknown tool requested by model: " + call.ProviderToolName},
		}
		emit(ToolEvent{Tool: call.ProviderToolName, Decision: "BLOCK",
			Reasons: []string{"Unknown tool requested by model"}})
		return provider.ToolResult{ProviderToolName: call.ProviderToolName, ToolCallID: call.ToolCallID, Content: content}, "BLOCK"
	}

	args := call.Args
	if args == nil {
		args = map[string]any{}
	}
	resource := pact.ResourceFromArgs(toolID, args)

	tokenHash, err := a.Client.IssueCapability(ctx, a.AgentID, a.intentHash, toolID, resource, 2, 300)
	if err != nil {
		emit(Err{Error: fmt.Errorf("issue capability: %w", err)})
		return provider.ToolResult{}, "BLOCK"
	}

	var parent any
	if a.parentHash != "" {
		parent = a.parentHash
	}
	ts := time.Now().UTC().Format("2006-01-02T15:04:05.000000+00:00")
	env := pact.NewEnvelope(a.AgentID, a.runID, a.stepID, toolID, args, a.intentHash, tokenHash, map[string]any{}, parent, ts)
	if err := env.Sign(a.privKey); err != nil {
		emit(Err{Error: fmt.Errorf("sign envelope: %w", err)})
		return provider.ToolResult{}, "BLOCK"
	}

	dec, err := a.Client.GatewayExecute(ctx, a.runID, env, approved)
	if err != nil {
		emit(Err{Error: fmt.Errorf("gateway: %w", err)})
		return provider.ToolResult{}, "BLOCK"
	}
	a.stepID++
	a.parentHash = dec.ActionHash

	content := map[string]any{
		"tool":        toolID,
		"args":        args,
		"decision":    dec.Decision,
		"risk_score":  dec.RiskScore,
		"severity":    dec.Severity,
		"reasons":     dec.Reasons,
		"action_hash": dec.ActionHash,
		"run_id":      dec.RunID,
		"approved":    approved,
	}

	var preview string
	if dec.Decision == "ALLOW" {
		toolResult := a.Runner.Execute(ctx, toolID, args)
		content["result"] = toolResult
		if err := a.Client.AttachResult(ctx, dec.ActionHash, toolResult); err != nil {
			// non-fatal: dashboard just won't show the result body
			content["result_attach_error"] = err.Error()
		}
		preview = previewJSON(toolResult)
	} else {
		content["result"] = nil
	}

	emit(ToolEvent{
		Tool: toolID, Decision: dec.Decision, Risk: dec.RiskScore, Severity: dec.Severity,
		Reasons: dec.Reasons, ResultPreview: preview, Approved: approved,
	})
	return provider.ToolResult{ProviderToolName: call.ProviderToolName, ToolCallID: call.ToolCallID, Content: content}, dec.Decision
}

// execTool is used on resume for an approved pending call (skip_approval=true).
func (a *Agent) execTool(ctx context.Context, providerToolName, toolCallID string, args map[string]any, approved bool, emit func(Event)) provider.ToolResult {
	tr, _ := a.execToolDecide(ctx, provider.ToolCall{ProviderToolName: providerToolName, ToolCallID: toolCallID, Args: args}, approved, emit)
	return tr
}

func (a *Agent) recordModelEvent(ctx context.Context, userText string, r provider.Result) {
	var calls []map[string]any
	for _, c := range r.ToolCalls {
		calls = append(calls, map[string]any{"name": c.ProviderToolName, "args": c.Args, "tool_call_id": c.ToolCallID})
	}
	reqJSON, _ := json.Marshal(map[string]any{"user_text": clip(userText, 500)})
	respJSON, _ := json.Marshal(map[string]any{"text": clip(r.Text, 1000)})
	_ = a.Client.RecordModelEvent(ctx, a.runID, a.Provider.Name(), a.Provider.Model(), string(reqJSON), string(respJSON), calls, r.TokenUsage)
}

func clip(s string, n int) string {
	if len(s) > n {
		return s[:n]
	}
	return s
}

func previewJSON(v any) string {
	raw, _ := json.Marshal(v)
	return clip(string(raw), 700)
}
