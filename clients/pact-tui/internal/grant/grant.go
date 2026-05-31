// Package grant mirrors backend/app/core/grants.py: an operator-controlled
// authority ceiling on tools and per-resource-type scope. The agent cannot widen
// it. DefaultGrant is deny-by-default for external sinks (no outbound email, no
// shell), which is what makes exfiltration structurally impossible out of the box.
package grant

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// Grant is an operator-authorized ceiling on tools and resource scopes.
//
// Tools is either the string "*" (all registered tools) or an explicit list.
// We model that with AllTools + Tools so YAML `tools: "*"` and `tools: [..]`
// both work.
type Grant struct {
	AllTools      bool
	Tools         []string
	ResourceScope map[string][]string
}

// raw is the on-disk YAML shape (tools may be "*" or a list).
type raw struct {
	Tools         any                 `yaml:"tools"`
	ResourceScope map[string][]string `yaml:"resource_scope"`
}

// AllowsTool reports whether the grant permits a tool id.
func (g Grant) AllowsTool(tool string) bool {
	if g.AllTools {
		return true
	}
	for _, t := range g.Tools {
		if t == tool {
			return true
		}
	}
	return false
}

// ToolCeiling returns the subset of allTools this grant permits.
func (g Grant) ToolCeiling(allTools []string) []string {
	if g.AllTools {
		out := make([]string, len(allTools))
		copy(out, allTools)
		return out
	}
	var out []string
	for _, t := range allTools {
		if g.AllowsTool(t) {
			out = append(out, t)
		}
	}
	return out
}

// Default is the built-in deny-by-default grant (matches Python DEFAULT_GRANT).
func Default() Grant {
	return Grant{
		AllTools: false,
		Tools:    []string{"file.read", "web.read", "email.read", "summarize", "respond_to_user"},
		ResourceScope: map[string][]string{
			"email_address": {},    // moot unless operator also grants email.send
			"email_id":      {"*"}, // reading the local inbox fixture is fine
			"file_path":     {"*"}, // repo-relative; traversal blocked by the tool layer
			"url":           {"*"}, // web reads allowed; enterprises typically restrict
			"command":       {},    // moot unless operator also grants shell.execute_mock
		},
	}
}

// Load reads an operator grant from a YAML file.
func Load(path string) (Grant, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Grant{}, err
	}
	var r raw
	if err := yaml.Unmarshal(data, &r); err != nil {
		return Grant{}, fmt.Errorf("parse grant %s: %w", path, err)
	}
	g := Grant{ResourceScope: r.ResourceScope}
	if g.ResourceScope == nil {
		g.ResourceScope = map[string][]string{}
	}
	switch t := r.Tools.(type) {
	case nil:
		g.AllTools = true
	case string:
		if t == "*" {
			g.AllTools = true
		} else {
			g.Tools = []string{t}
		}
	case []any:
		for _, v := range t {
			if s, ok := v.(string); ok {
				g.Tools = append(g.Tools, s)
			}
		}
	default:
		return Grant{}, fmt.Errorf("grant 'tools' must be \"*\" or a list, got %T", r.Tools)
	}
	return g, nil
}
