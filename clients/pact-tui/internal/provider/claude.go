package provider

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

type claudeProvider struct {
	apiKey string
	model  string
	http   *http.Client
}

func newClaude(model string) (Provider, error) {
	key := os.Getenv("CLAUDE_API_KEY")
	if key == "" {
		return nil, fmt.Errorf("CLAUDE_API_KEY is not configured")
	}
	m := firstNonEmpty(model, os.Getenv("CLAUDE_MODEL"), "claude-3-5-sonnet-latest")
	return &claudeProvider{apiKey: key, model: m, http: &http.Client{Timeout: 90 * time.Second}}, nil
}

func (p *claudeProvider) Name() string  { return "claude" }
func (p *claudeProvider) Model() string { return p.model }

func (p *claudeProvider) claudeTools() []map[string]any {
	out := make([]map[string]any, 0, len(toolDeclarations()))
	for _, t := range toolDeclarations() {
		out = append(out, map[string]any{"name": t.Name, "description": t.Description, "input_schema": t.InputSchema})
	}
	return out
}

func (p *claudeProvider) Complete(ctx context.Context, messages []any) (Result, error) {
	body := map[string]any{
		"model":      p.model,
		"max_tokens": 1024,
		"system":     SystemPrompt,
		"messages":   messages,
		"tools":      p.claudeTools(),
	}
	raw, err := postJSON(ctx, p.http, "https://api.anthropic.com/v1/messages", map[string]string{
		"x-api-key":         p.apiKey,
		"anthropic-version": "2023-06-01",
		"content-type":      "application/json",
	}, body)
	if err != nil {
		return Result{}, err
	}
	var text strings.Builder
	var calls []ToolCall
	if content, ok := raw["content"].([]any); ok {
		for _, b := range content {
			block, _ := b.(map[string]any)
			switch block["type"] {
			case "text":
				text.WriteString(asString(block["text"]))
			case "tool_use":
				args, _ := block["input"].(map[string]any)
				if args == nil {
					args = map[string]any{}
				}
				calls = append(calls, ToolCall{
					ProviderToolName: asString(block["name"]),
					ToolCallID:       asString(block["id"]),
					Args:             args,
				})
			}
		}
	}
	usage, _ := raw["usage"].(map[string]any)
	return Result{Text: strings.TrimSpace(text.String()), ToolCalls: calls, Raw: raw, TokenUsage: usage}, nil
}

func (p *claudeProvider) AppendAssistant(messages *[]any, r Result) {
	content := r.Raw["content"]
	if content == nil {
		content = []any{}
	}
	*messages = append(*messages, map[string]any{"role": "assistant", "content": content})
}

func (p *claudeProvider) AppendToolResults(messages *[]any, results []ToolResult) {
	var content []any
	for _, res := range results {
		if res.ToolCallID == "" {
			continue
		}
		payload, _ := json.Marshal(res.Content)
		content = append(content, map[string]any{
			"type":        "tool_result",
			"tool_use_id": res.ToolCallID,
			"content":     string(payload),
			"is_error":    asString(res.Content["decision"]) != "ALLOW",
		})
	}
	*messages = append(*messages, map[string]any{"role": "user", "content": content})
}

func (p *claudeProvider) UserMessage(text string) any {
	return map[string]any{"role": "user", "content": text}
}

// --- shared helpers ---

func postJSON(ctx context.Context, client *http.Client, url string, headers map[string]string, body any) (map[string]any, error) {
	raw, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(raw))
	if err != nil {
		return nil, err
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("provider HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(data)))
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, fmt.Errorf("decode provider response: %w", err)
	}
	return out, nil
}

func asString(v any) string {
	if s, ok := v.(string); ok {
		return s
	}
	return ""
}
