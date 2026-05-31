package ui

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
)

func TestRenderMarkdownFormatsCodeBlocks(t *testing.T) {
	out := renderMarkdown("## Summary\n\nUse `go test`:\n\n```go\nfunc main() {\n\tprintln(\"ok\")\n}\n```", 64)

	for _, want := range []string{"Summary", "go test", " go ", "func main()"} {
		if !strings.Contains(out, want) {
			t.Fatalf("rendered markdown missing %q:\n%s", want, out)
		}
	}
	if lipgloss.Width(out) > 80 {
		t.Fatalf("rendered markdown is unexpectedly wide: %d\n%s", lipgloss.Width(out), out)
	}
}

func TestRenderMarkdownFormatsListsAndQuotes(t *testing.T) {
	out := renderMarkdown("> blocked by policy\n\n- first\n- second", 48)

	for _, want := range []string{"blocked by policy", "• first", "• second"} {
		if !strings.Contains(out, want) {
			t.Fatalf("rendered markdown missing %q:\n%s", want, out)
		}
	}
}
