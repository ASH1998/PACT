package provider

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"net/http"
	"os"
	"strings"
	"time"
)

type geminiProvider struct {
	apiKey  string
	model   string
	baseURL string
	http    *http.Client
}

func newGemini(model string) (Provider, error) {
	key := firstNonEmpty(os.Getenv("GOOGLE_API_KEY"), os.Getenv("GEMINI_API_KEY"))
	if key == "" {
		return nil, fmt.Errorf("GOOGLE_API_KEY or GEMINI_API_KEY is not configured")
	}
	m := firstNonEmpty(model, os.Getenv("GOOGLE_MODEL"), os.Getenv("GEMINI_MODEL"), "gemini-pro")
	base := firstNonEmpty(os.Getenv("GEMINI_API_URL"), "https://generativelanguage.googleapis.com")
	return &geminiProvider{apiKey: key, model: m, baseURL: base, http: &http.Client{Timeout: 90 * time.Second}}, nil
}

func (p *geminiProvider) Name() string  { return "gemini" }
func (p *geminiProvider) Model() string { return p.model }

func (p *geminiProvider) Complete(ctx context.Context, messages []any) (Result, error) {
	decls := make([]map[string]any, 0, len(toolDeclarations()))
	for _, t := range toolDeclarations() {
		decls = append(decls, map[string]any{"name": t.Name, "description": t.Description, "parameters": t.InputSchema})
	}
	body := map[string]any{
		"systemInstruction": map[string]any{"parts": []any{map[string]any{"text": SystemPrompt}}},
		"contents":          messages,
		"tools":             []any{map[string]any{"functionDeclarations": decls}},
		"generationConfig":  map[string]any{"temperature": 0.2},
	}
	url := fmt.Sprintf("%s/v1beta/models/%s:generateContent", strings.TrimRight(p.baseURL, "/"), p.model)
	raw, err := postJSON(ctx, p.http, url, map[string]string{
		"x-goog-api-key": p.apiKey,
		"content-type":   "application/json",
	}, body)
	if err != nil {
		return Result{}, err
	}
	var text strings.Builder
	var calls []ToolCall
	candidates, _ := raw["candidates"].([]any)
	if len(candidates) > 0 {
		cand, _ := candidates[0].(map[string]any)
		content, _ := cand["content"].(map[string]any)
		parts, _ := content["parts"].([]any)
		for _, pt := range parts {
			part, _ := pt.(map[string]any)
			if t, ok := part["text"]; ok {
				text.WriteString(asString(t))
			} else if fc, ok := part["functionCall"].(map[string]any); ok {
				args, _ := fc["args"].(map[string]any)
				if args == nil {
					args = map[string]any{}
				}
				calls = append(calls, ToolCall{
					ProviderToolName: asString(fc["name"]),
					ToolCallID:       "gemini_" + randHex(8),
					Args:             args,
				})
			}
		}
	}
	usage, _ := raw["usageMetadata"].(map[string]any)
	return Result{Text: strings.TrimSpace(text.String()), ToolCalls: calls, Raw: raw, TokenUsage: usage}, nil
}

func (p *geminiProvider) AppendAssistant(messages *[]any, r Result) {
	candidates, _ := r.Raw["candidates"].([]any)
	if len(candidates) > 0 {
		cand, _ := candidates[0].(map[string]any)
		if content, ok := cand["content"]; ok && content != nil {
			*messages = append(*messages, content)
		}
	}
}

func (p *geminiProvider) AppendToolResults(messages *[]any, results []ToolResult) {
	var parts []any
	for _, res := range results {
		parts = append(parts, map[string]any{
			"functionResponse": map[string]any{
				"name":     res.ProviderToolName,
				"response": map[string]any{"result": res.Content},
			},
		})
	}
	*messages = append(*messages, map[string]any{"role": "user", "parts": parts})
}

func (p *geminiProvider) UserMessage(text string) any {
	return map[string]any{"role": "user", "parts": []any{map[string]any{"text": text}}}
}

func randHex(n int) string {
	b := make([]byte, (n+1)/2)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)[:n]
}
