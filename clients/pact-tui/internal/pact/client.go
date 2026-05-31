package pact

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// Client is a thin HTTP client for the PACT backend v1 API.
type Client struct {
	BaseURL string
	HTTP    *http.Client
}

// NewClient returns a client for the given backend base URL (e.g.
// http://localhost:8000).
func NewClient(baseURL string) *Client {
	return &Client{
		BaseURL: strings.TrimRight(baseURL, "/"),
		HTTP:    &http.Client{Timeout: 100 * time.Second},
	}
}

func (c *Client) do(ctx context.Context, method, path string, body any, out any) error {
	var rdr io.Reader
	if body != nil {
		raw, err := json.Marshal(body)
		if err != nil {
			return err
		}
		rdr = bytes.NewReader(raw)
	}
	req, err := http.NewRequestWithContext(ctx, method, c.BaseURL+path, rdr)
	if err != nil {
		return err
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return fmt.Errorf("%s %s: %w", method, path, err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return fmt.Errorf("%s %s: HTTP %d: %s", method, path, resp.StatusCode, strings.TrimSpace(string(data)))
	}
	if out != nil && len(data) > 0 {
		if err := json.Unmarshal(data, out); err != nil {
			return fmt.Errorf("%s %s: decode response: %w", method, path, err)
		}
	}
	return nil
}

// Health returns nil if the backend is reachable and healthy.
func (c *Client) Health(ctx context.Context) error {
	return c.do(ctx, http.MethodGet, "/health", nil, nil)
}

// RegisterAgent registers a passport via the runtime and returns the agent's
// base64 Ed25519 private key (the nacl seed).
func (c *Client) RegisterAgent(ctx context.Context, agentID, owner, agentType string, allowedDomains []string) (string, error) {
	var out struct {
		AgentPrivateKey string `json:"agent_private_key"`
	}
	body := map[string]any{
		"agent_id":        agentID,
		"owner":           owner,
		"agent_type":      agentType,
		"allowed_domains": allowedDomains,
	}
	if err := c.do(ctx, http.MethodPost, "/v1/agents/register", body, &out); err != nil {
		return "", err
	}
	return out.AgentPrivateKey, nil
}

// ToolMeta is the registration metadata for a tool.
type ToolMeta struct {
	ToolID           string
	Name             string
	Description      string
	SideEffect       string
	Sensitivity      string
	ResourceType     string
	RequiresApproval bool
}

// RegisterTool registers (upserts) a tool's enforcement metadata so the gateway
// knows its resource_type/sensitivity.
func (c *Client) RegisterTool(ctx context.Context, m ToolMeta) error {
	body := map[string]any{
		"tool_id":           m.ToolID,
		"name":              m.Name,
		"description":       m.Description,
		"side_effect":       m.SideEffect,
		"sensitivity":       m.Sensitivity,
		"resource_type":     m.ResourceType,
		"requires_approval": m.RequiresApproval,
	}
	return c.do(ctx, http.MethodPost, "/v1/tools/register", body, nil)
}

// CreateIntent creates a programmatic intent with an operator resource scope and
// returns the intent hash.
func (c *Client) CreateIntent(ctx context.Context, userGoal, createdBy string, allowed, forbidden []string, resourceScope map[string][]string) (string, error) {
	if allowed == nil {
		allowed = []string{}
	}
	if forbidden == nil {
		forbidden = []string{}
	}
	if resourceScope == nil {
		resourceScope = map[string][]string{}
	}
	var out struct {
		IntentHash string `json:"intent_hash"`
	}
	body := map[string]any{
		"user_goal":         userGoal,
		"created_by":        createdBy,
		"allowed_actions":   allowed,
		"forbidden_actions": forbidden,
		"resource_scope":    resourceScope,
	}
	if err := c.do(ctx, http.MethodPost, "/v1/intents", body, &out); err != nil {
		return "", err
	}
	return out.IntentHash, nil
}

// CreateRun creates a run and returns its id.
func (c *Client) CreateRun(ctx context.Context, agentID, scenario, userGoal string) (string, error) {
	var out struct {
		RunID string `json:"run_id"`
	}
	body := map[string]any{"agent_id": agentID, "scenario_name": scenario, "user_goal": userGoal}
	if err := c.do(ctx, http.MethodPost, "/v1/runs", body, &out); err != nil {
		return "", err
	}
	return out.RunID, nil
}

// IssueCapability issues a capability token and returns its hash.
func (c *Client) IssueCapability(ctx context.Context, agentID, intentHash, capability, resource string, maxUses, ttlSeconds int) (string, error) {
	var out struct {
		TokenHash string `json:"token_hash"`
	}
	body := map[string]any{
		"agent_id":    agentID,
		"intent_hash": intentHash,
		"capability":  capability,
		"resource":    resource,
		"max_uses":    maxUses,
		"ttl_seconds": ttlSeconds,
	}
	if err := c.do(ctx, http.MethodPost, "/v1/capabilities", body, &out); err != nil {
		return "", err
	}
	return out.TokenHash, nil
}

// Decision is the gateway's verdict for a submitted envelope.
type Decision struct {
	Decision   string   `json:"decision"`
	RiskScore  int      `json:"risk_score"`
	Severity   string   `json:"severity"`
	Reasons    []string `json:"reasons"`
	ActionHash string   `json:"action_hash"`
	RunID      string   `json:"run_id"`
}

// GatewayExecute submits a client-signed envelope through the gateway (no
// server-side tool execution) and returns the authoritative decision.
func (c *Client) GatewayExecute(ctx context.Context, runID string, env Envelope, skipApproval bool) (Decision, error) {
	var out Decision
	body := map[string]any{"run_id": runID, "envelope": map[string]any(env), "skip_approval": skipApproval}
	err := c.do(ctx, http.MethodPost, "/v1/gateway/execute", body, &out)
	return out, err
}

// AttachResult attaches a client-executed tool result to an action.
func (c *Client) AttachResult(ctx context.Context, actionHash string, result map[string]any) error {
	if result == nil {
		result = map[string]any{}
	}
	return c.do(ctx, http.MethodPost, "/v1/actions/"+actionHash+"/result", map[string]any{"result": result}, nil)
}

// RecordModelEvent records a model interaction for the dashboard.
func (c *Client) RecordModelEvent(ctx context.Context, runID, provider, model, requestJSON, responseJSON string, toolCalls []map[string]any, tokenUsage map[string]any) error {
	body := map[string]any{
		"provider":      provider,
		"model":         model,
		"request_json":  requestJSON,
		"response_json": responseJSON,
		"tool_calls":    toolCalls,
		"token_usage":   tokenUsage,
	}
	return c.do(ctx, http.MethodPost, "/v1/runs/"+runID+"/model-events", body, nil)
}

// CompleteRun marks a run completed.
func (c *Client) CompleteRun(ctx context.Context, runID string) error {
	return c.do(ctx, http.MethodPost, "/v1/runs/"+runID+"/complete", nil, nil)
}

// Ledger is the result of a hash-chain verification.
type Ledger struct {
	RunID  string   `json:"run_id"`
	Valid  bool     `json:"valid"`
	Issues []string `json:"issues"`
}

// VerifyLedger verifies the run's hash-chained ledger.
func (c *Client) VerifyLedger(ctx context.Context, runID string) (Ledger, error) {
	var out Ledger
	err := c.do(ctx, http.MethodGet, "/v1/runs/"+runID+"/ledger/verify", nil, &out)
	return out, err
}

// ResourceFromArgs mirrors backend app.tools.resource.resource_from_args so the
// client binds capabilities to the same resource string the gateway extracts.
func ResourceFromArgs(tool string, args map[string]any) string {
	get := func(keys ...string) string {
		for _, k := range keys {
			if v, ok := args[k]; ok {
				if s, ok := v.(string); ok && s != "" {
					return s
				}
			}
		}
		return "default"
	}
	switch {
	case strings.HasPrefix(tool, "email."):
		return get("email_id", "to")
	case strings.HasPrefix(tool, "file."):
		return get("path")
	case strings.HasPrefix(tool, "web."):
		return get("url")
	case strings.HasPrefix(tool, "shell."):
		return get("command")
	default:
		return "default"
	}
}
