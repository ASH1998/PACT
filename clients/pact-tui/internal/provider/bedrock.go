package provider

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"sort"
	"strings"
	"time"
)

type bedrockProvider struct {
	accessKey    string
	secretKey    string
	sessionToken string
	region       string
	model        string
	http         *http.Client
}

func newBedrock(model string) (Provider, error) {
	m := firstNonEmpty(model, os.Getenv("CLAUDE_MODEL"))
	if m == "" {
		return nil, fmt.Errorf("CLAUDE_MODEL is not configured")
	}
	ak := os.Getenv("AWS_ACCESS_KEY_ID")
	sk := os.Getenv("AWS_SECRET_ACCESS_KEY")
	if ak == "" || sk == "" {
		return nil, fmt.Errorf("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required for Bedrock Claude")
	}
	return &bedrockProvider{
		accessKey:    ak,
		secretKey:    sk,
		sessionToken: os.Getenv("AWS_SESSION_TOKEN"),
		region:       firstNonEmpty(os.Getenv("AWS_REGION"), "us-east-1"),
		model:        m,
		http:         &http.Client{Timeout: 90 * time.Second},
	}, nil
}

func (p *bedrockProvider) Name() string  { return "bedrock" }
func (p *bedrockProvider) Model() string { return p.model }

func hmacSHA256(key, data []byte) []byte {
	h := hmac.New(sha256.New, key)
	h.Write(data)
	return h.Sum(nil)
}

func (p *bedrockProvider) signingKey(dateStamp string) []byte {
	kDate := hmacSHA256([]byte("AWS4"+p.secretKey), []byte(dateStamp))
	kRegion := hmacSHA256(kDate, []byte(p.region))
	kService := hmacSHA256(kRegion, []byte("bedrock"))
	return hmacSHA256(kService, []byte("aws4_request"))
}

// quote mirrors Python urllib.parse.quote(s, safe=safe).
func quote(s, safe string) string {
	const always = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~"
	safeSet := always + "/" + safe
	var b strings.Builder
	for i := 0; i < len(s); i++ {
		c := s[i]
		if strings.IndexByte(safeSet, c) >= 0 {
			b.WriteByte(c)
		} else {
			b.WriteString(fmt.Sprintf("%%%02X", c))
		}
	}
	return b.String()
}

func (p *bedrockProvider) headers(method, canonicalPath string, body []byte) map[string]string {
	host := fmt.Sprintf("bedrock-runtime.%s.amazonaws.com", p.region)
	now := time.Now().UTC()
	amzDate := now.Format("20060102T150405Z")
	dateStamp := now.Format("20060102")
	payloadHash := hex.EncodeToString(func() []byte { s := sha256.Sum256(body); return s[:] }())

	headers := map[string]string{
		"content-type": "application/json",
		"host":         host,
		"x-amz-date":   amzDate,
	}
	if p.sessionToken != "" {
		headers["x-amz-security-token"] = p.sessionToken
	}

	keys := make([]string, 0, len(headers))
	for k := range headers {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	var canonHeaders strings.Builder
	for _, k := range keys {
		canonHeaders.WriteString(k + ":" + headers[k] + "\n")
	}
	signedHeaders := strings.Join(keys, ";")
	canonicalRequest := strings.Join([]string{method, canonicalPath, "", canonHeaders.String(), signedHeaders, payloadHash}, "\n")
	credentialScope := fmt.Sprintf("%s/%s/bedrock/aws4_request", dateStamp, p.region)
	crHash := sha256.Sum256([]byte(canonicalRequest))
	stringToSign := strings.Join([]string{"AWS4-HMAC-SHA256", amzDate, credentialScope, hex.EncodeToString(crHash[:])}, "\n")
	signature := hex.EncodeToString(hmacSHA256(p.signingKey(dateStamp), []byte(stringToSign)))
	headers["authorization"] = fmt.Sprintf(
		"AWS4-HMAC-SHA256 Credential=%s/%s, SignedHeaders=%s, Signature=%s",
		p.accessKey, credentialScope, signedHeaders, signature,
	)
	return headers
}

func (p *bedrockProvider) Complete(ctx context.Context, messages []any) (Result, error) {
	specs := make([]map[string]any, 0, len(toolDeclarations()))
	for _, t := range toolDeclarations() {
		specs = append(specs, map[string]any{"toolSpec": map[string]any{
			"name": t.Name, "description": t.Description, "inputSchema": map[string]any{"json": t.InputSchema},
		}})
	}
	bodyDict := map[string]any{
		"modelId":         p.model,
		"system":          []any{map[string]any{"text": SystemPrompt}},
		"messages":        messages,
		"toolConfig":      map[string]any{"tools": specs},
		"inferenceConfig": map[string]any{"maxTokens": 1024, "temperature": 0.2},
	}
	body, err := json.Marshal(bodyDict)
	if err != nil {
		return Result{}, err
	}
	urlPath := "/model/" + quote(p.model, ":.") + "/converse"
	canonicalPath := "/model/" + quote(p.model, ".") + "/converse"
	url := fmt.Sprintf("https://bedrock-runtime.%s.amazonaws.com%s", p.region, urlPath)
	raw, err := p.post(ctx, url, canonicalPath, body)
	if err != nil {
		return Result{}, err
	}

	var text strings.Builder
	var calls []ToolCall
	output, _ := raw["output"].(map[string]any)
	message, _ := output["message"].(map[string]any)
	content, _ := message["content"].([]any)
	for _, b := range content {
		block, _ := b.(map[string]any)
		if t, ok := block["text"]; ok {
			text.WriteString(asString(t))
		} else if tu, ok := block["toolUse"].(map[string]any); ok {
			args, _ := tu["input"].(map[string]any)
			if args == nil {
				args = map[string]any{}
			}
			calls = append(calls, ToolCall{
				ProviderToolName: asString(tu["name"]),
				ToolCallID:       asString(tu["toolUseId"]),
				Args:             args,
			})
		}
	}
	usage, _ := raw["usage"].(map[string]any)
	return Result{Text: strings.TrimSpace(text.String()), ToolCalls: calls, Raw: raw, TokenUsage: usage}, nil
}

func (p *bedrockProvider) post(ctx context.Context, url, canonicalPath string, body []byte) (map[string]any, error) {
	headers := p.headers("POST", canonicalPath, body)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, strings.NewReader(string(body)))
	if err != nil {
		return nil, err
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := p.http.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("bedrock HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(data)))
	}
	var out map[string]any
	if err := json.Unmarshal(data, &out); err != nil {
		return nil, fmt.Errorf("decode bedrock response: %w", err)
	}
	return out, nil
}

func (p *bedrockProvider) AppendAssistant(messages *[]any, r Result) {
	output, _ := r.Raw["output"].(map[string]any)
	if message, ok := output["message"]; ok && message != nil {
		*messages = append(*messages, message)
	}
}

func (p *bedrockProvider) AppendToolResults(messages *[]any, results []ToolResult) {
	var content []any
	for _, res := range results {
		if res.ToolCallID == "" {
			continue
		}
		status := "error"
		if asString(res.Content["decision"]) == "ALLOW" {
			status = "success"
		}
		content = append(content, map[string]any{
			"toolResult": map[string]any{
				"toolUseId": res.ToolCallID,
				"status":    status,
				"content":   []any{map[string]any{"json": res.Content}},
			},
		})
	}
	*messages = append(*messages, map[string]any{"role": "user", "content": content})
}

func (p *bedrockProvider) UserMessage(text string) any {
	return map[string]any{"role": "user", "content": []any{map[string]any{"text": text}}}
}
