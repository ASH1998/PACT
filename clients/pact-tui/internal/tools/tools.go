// Package tools ports the local tool implementations from pact_chat.py. These
// run on the client machine; PACT decides whether each call is allowed before
// the result is used. Tool ids, metadata, and provider-facing specs mirror the
// Python CLI so behavior is identical.
package tools

import (
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/smtp"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

// Tool ids (PACT) <-> provider tool names (LLM function names).
var NameToID = map[string]string{
	"email_read":         "email.read",
	"email_send":         "email.send",
	"web_read":           "web.read",
	"file_read":          "file.read",
	"file_read_secret":   "file.read_secret",
	"shell_execute_mock": "shell.execute_mock",
	"summarize":          "summarize",
	"respond_to_user":    "respond_to_user",
}

// IDToName is the reverse of NameToID.
var IDToName = func() map[string]string {
	m := map[string]string{}
	for k, v := range NameToID {
		m[v] = k
	}
	return m
}()

// Meta describes a tool's PACT enforcement metadata (mirrors TOOL_METADATA).
type Meta struct {
	DisplayName      string
	Description      string
	SideEffect       string
	ResourceType     string
	Sensitivity      string
	RequiresApproval bool
}

// Metadata for the seven enforced tools.
var Metadata = map[string]Meta{
	"email.read":         {"Read Email", "Read configured local email data.", "read", "email_id", "medium", false},
	"email.send":         {"Send Email", "Send email through configured SMTP.", "external_write", "email_address", "high", false},
	"web.read":           {"Read Web Page", "Fetch a real HTTP(S) page.", "read", "url", "medium", false},
	"file.read":          {"Read File", "Read a local non-secret file.", "read", "file_path", "low", false},
	"file.read_secret":   {"Read Secret File", "Read a local secret file with redaction.", "read", "file_path", "critical", true},
	"shell.execute_mock": {"Execute Shell Command", "Execute a local shell command after approval.", "shell", "command", "critical", true},
	"summarize":          {"Summarize Text", "Create a short extractive summary.", "none", "default", "low", false},
}

// Spec is a provider-facing tool declaration.
type Spec struct {
	Name        string
	Description string
	InputSchema map[string]any
}

func strProp() map[string]any { return map[string]any{"type": "string"} }

// Specs are the tool declarations sent to the LLM (mirror TOOL_SPECS).
var Specs = []Spec{
	{"email_read", "Read email only from a configured local JSON fixture. If no fixture is configured, returns not_configured instead of fake email.",
		map[string]any{"type": "object", "properties": map[string]any{"email_id": strProp()}, "required": []string{}}},
	{"email_send", "Send email through SMTP only when SMTP_HOST is configured. Otherwise returns not_sent instead of pretending to send.",
		map[string]any{"type": "object", "properties": map[string]any{"to": strProp(), "subject": strProp(), "body": strProp()}, "required": []string{"to"}}},
	{"web_read", "Fetch a real web page over HTTP(S) and return status, title, and extracted text.",
		map[string]any{"type": "object", "properties": map[string]any{"url": strProp()}, "required": []string{}}},
	{"file_read", "Read a real local file from the current repository. Secret-looking files are refused; use file_read_secret for explicit secret reads.",
		map[string]any{"type": "object", "properties": map[string]any{"path": strProp()}, "required": []string{}}},
	{"file_read_secret", "Read a real local secret file, but return redacted values and digests rather than raw secrets.",
		map[string]any{"type": "object", "properties": map[string]any{"path": strProp()}, "required": []string{}}},
	{"shell_execute_mock", "Run a real shell command after PACT and local human approval. Output is captured with a timeout.",
		map[string]any{"type": "object", "properties": map[string]any{"command": strProp()}, "required": []string{"command"}}},
	{"summarize", "Summarize provided text.",
		map[string]any{"type": "object", "properties": map[string]any{"text": strProp()}, "required": []string{"text"}}},
}

// AllowedToolIDs is the universe of tool ids the CLI exposes.
var AllowedToolIDs = func() []string {
	ids := make([]string, 0, len(Specs))
	for _, s := range Specs {
		ids = append(ids, NameToID[s.Name])
	}
	return ids
}()

// Runner executes tools locally against a repo root and environment config.
type Runner struct {
	RepoRoot string
	HTTP     *http.Client
}

// NewRunner returns a Runner rooted at repoRoot.
func NewRunner(repoRoot string) *Runner {
	abs, err := filepath.Abs(repoRoot)
	if err != nil {
		abs = repoRoot
	}
	return &Runner{RepoRoot: abs, HTTP: &http.Client{Timeout: 20 * time.Second}}
}

// Execute runs a tool by PACT id and returns its result object.
func (r *Runner) Execute(ctx context.Context, toolID string, args map[string]any) map[string]any {
	switch toolID {
	case "web.read":
		return r.webRead(ctx, str(args, "url", "https://example.com"))
	case "file.read":
		return r.fileRead(str(args, "path", "README.md"))
	case "file.read_secret":
		return r.fileReadSecret(str(args, "path", ".env"))
	case "email.read":
		return r.emailRead(str(args, "email_id", "latest"))
	case "email.send":
		return r.emailSend(str(args, "to", ""), str(args, "subject", ""), str(args, "body", ""))
	case "shell.execute_mock":
		return r.shellExecute(ctx, str(args, "command", "uname -a"))
	case "summarize":
		return summarize(str(args, "text", ""))
	case "respond_to_user":
		return map[string]any{"type": "response", "message": str(args, "message", "")}
	default:
		return map[string]any{"status": "error", "error": "unknown tool: " + toolID}
	}
}

func str(m map[string]any, key, def string) string {
	if v, ok := m[key]; ok {
		if s, ok := v.(string); ok && s != "" {
			return s
		}
	}
	return def
}

func (r *Runner) safeRepoPath(path string) (string, error) {
	candidate := filepath.Clean(filepath.Join(r.RepoRoot, path))
	root := filepath.Clean(r.RepoRoot)
	if candidate != root && !strings.HasPrefix(candidate, root+string(os.PathSeparator)) {
		return "", fmt.Errorf("path escapes repository root")
	}
	return candidate, nil
}

var secretNames = []string{".env", "secret", "credential", "token", "key", "pem"}

func looksSecret(path string) bool {
	low := strings.ToLower(path)
	for _, n := range secretNames {
		if strings.Contains(low, n) {
			return true
		}
	}
	return false
}

var secretLine = regexp.MustCompile(`(?m)^([A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|DATABASE_URL|API)[A-Z0-9_]*)=(.+)$`)

func redact(text string) (string, []map[string]any) {
	var findings []map[string]any
	out := secretLine.ReplaceAllStringFunc(text, func(line string) string {
		m := secretLine.FindStringSubmatch(line)
		key, val := m[1], m[2]
		sum := sha256.Sum256([]byte(val))
		digest := fmt.Sprintf("%x", sum)[:12]
		findings = append(findings, map[string]any{"key": key, "digest": "sha256:" + digest, "length": fmt.Sprintf("%d", len(val))})
		return fmt.Sprintf("%s=<redacted:%s>", key, digest)
	})
	return out, findings
}

func clip(s string, n int) (string, bool) {
	if len(s) > n {
		return s[:n], true
	}
	return s, false
}

func (r *Runner) fileRead(path string) map[string]any {
	if looksSecret(path) {
		return map[string]any{"status": "refused", "path": path,
			"reason": "Path looks secret; use file_read_secret for explicit secret handling."}
	}
	target, err := r.safeRepoPath(path)
	if err != nil {
		return errResult(path, err)
	}
	data, err := os.ReadFile(target)
	if err != nil {
		return errResult(path, err)
	}
	rel, _ := filepath.Rel(r.RepoRoot, target)
	content, trunc := clip(string(data), 8000)
	return map[string]any{"type": "file_content", "status": "ok", "path": rel,
		"content": content, "size_bytes": len(data), "truncated": trunc}
}

func (r *Runner) fileReadSecret(path string) map[string]any {
	target, err := r.safeRepoPath(path)
	if err != nil {
		return errResult(path, err)
	}
	data, err := os.ReadFile(target)
	if err != nil {
		return errResult(path, err)
	}
	rel, _ := filepath.Rel(r.RepoRoot, target)
	red, findings := redact(string(data))
	content, trunc := clip(red, 8000)
	if findings == nil {
		findings = []map[string]any{}
	}
	return map[string]any{"type": "secret_file_content", "status": "redacted", "path": rel,
		"content_redacted": content, "secret_findings": findings, "size_bytes": len(data), "truncated": trunc}
}

func (r *Runner) emailRead(emailID string) map[string]any {
	fixture := os.Getenv("PACT_EMAIL_JSON")
	if fixture == "" {
		return map[string]any{"status": "not_configured",
			"reason": "No email inbox fixture or provider is configured. Set PACT_EMAIL_JSON to a local JSON file."}
	}
	target, err := r.safeRepoPath(fixture)
	if err != nil {
		return errResult(fixture, err)
	}
	data, err := os.ReadFile(target)
	if err != nil {
		return errResult(fixture, err)
	}
	var asList []map[string]any
	if err := json.Unmarshal(data, &asList); err == nil {
		if len(asList) == 0 {
			return map[string]any{"status": "empty"}
		}
		if emailID == "latest" {
			return asList[len(asList)-1]
		}
		for _, item := range asList {
			if fmt.Sprintf("%v", item["id"]) == emailID {
				return item
			}
		}
		return map[string]any{"status": "not_found"}
	}
	var asObj map[string]any
	if err := json.Unmarshal(data, &asObj); err == nil {
		return asObj
	}
	return map[string]any{"status": "error", "error": "invalid email fixture JSON"}
}

func (r *Runner) emailSend(to, subject, body string) map[string]any {
	host := os.Getenv("SMTP_HOST")
	from := os.Getenv("SMTP_FROM")
	if host == "" || from == "" {
		return map[string]any{"type": "email_send", "status": "not_sent",
			"reason": "SMTP_HOST and SMTP_FROM are not configured; no email was sent.",
			"to":     to, "subject": subject}
	}
	port := os.Getenv("SMTP_PORT")
	if port == "" {
		port = "587"
	}
	addr := host + ":" + port
	msg := fmt.Sprintf("From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n%s\r\n", from, to, subject, body)
	var auth smtp.Auth
	if u := os.Getenv("SMTP_USERNAME"); u != "" {
		auth = smtp.PlainAuth("", u, os.Getenv("SMTP_PASSWORD"), host)
	}
	if err := smtp.SendMail(addr, auth, from, []string{to}, []byte(msg)); err != nil {
		return map[string]any{"type": "email_send", "status": "error", "to": to, "error": err.Error()}
	}
	return map[string]any{"type": "email_send", "status": "sent", "to": to, "subject": subject}
}

func (r *Runner) shellExecute(ctx context.Context, command string) map[string]any {
	cctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	cmd := exec.CommandContext(cctx, "sh", "-c", command)
	cmd.Dir = r.RepoRoot
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	exitCode := 0
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			exitCode = ee.ExitCode()
		} else {
			return map[string]any{"type": "shell_output", "command": command, "status": "error", "error": err.Error()}
		}
	}
	so := stdout.String()
	se := stderr.String()
	if len(so) > 8000 {
		so = so[len(so)-8000:]
	}
	if len(se) > 4000 {
		se = se[len(se)-4000:]
	}
	return map[string]any{"type": "shell_output", "command": command, "exit_code": exitCode, "stdout": so, "stderr": se}
}

func summarize(text string) map[string]any {
	words := strings.Fields(text)
	limit := 80
	suffix := ""
	if len(words) > limit {
		suffix = "..."
		words = words[:limit]
	}
	return map[string]any{"type": "summary", "text": strings.Join(words, " ") + suffix, "source_chars": len(text)}
}

func errResult(path string, err error) map[string]any {
	return map[string]any{"status": "error", "path": path, "error": err.Error()}
}

var (
	scriptStyle = regexp.MustCompile(`(?is)<(script|style|noscript)[^>]*>.*?</(script|style|noscript)>`)
	titleRe     = regexp.MustCompile(`(?is)<title[^>]*>(.*?)</title>`)
	tagRe       = regexp.MustCompile(`(?s)<[^>]+>`)
	wsRe        = regexp.MustCompile(`\s+`)
)

func (r *Runner) webRead(ctx context.Context, rawURL string) map[string]any {
	u := rawURL
	if !strings.Contains(u, "://") {
		u = "https://" + u
	}
	if !strings.HasPrefix(u, "http://") && !strings.HasPrefix(u, "https://") {
		return map[string]any{"status": "error", "error": "Only http and https URLs are supported", "url": rawURL}
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u, nil)
	if err != nil {
		return map[string]any{"status": "error", "url": u, "error": err.Error()}
	}
	req.Header.Set("User-Agent", "PACT-CLI-Agent/0.1")
	resp, err := r.HTTP.Do(req)
	if err != nil {
		return map[string]any{"status": "error", "url": u, "error": err.Error()}
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 200_000))
	ctype := resp.Header.Get("Content-Type")
	body := string(raw)
	title := ""
	text := body
	if strings.Contains(ctype, "html") {
		if m := titleRe.FindStringSubmatch(body); m != nil {
			title = strings.TrimSpace(wsRe.ReplaceAllString(m[1], " "))
		}
		stripped := scriptStyle.ReplaceAllString(body, " ")
		stripped = tagRe.ReplaceAllString(stripped, " ")
		text = strings.TrimSpace(wsRe.ReplaceAllString(stripped, " "))
	}
	content, trunc := clip(text, 6000)
	return map[string]any{"type": "web_content", "status": "ok", "url": resp.Request.URL.String(),
		"http_status": resp.StatusCode, "content_type": ctype, "title": title,
		"content": content, "truncated": trunc}
}
