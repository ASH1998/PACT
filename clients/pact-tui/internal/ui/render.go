package ui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/viewport"
	"github.com/charmbracelet/lipgloss"

	"pacttui/internal/agent"
	"pacttui/internal/tools"
)

const (
	sidebarW = 32
	gutterX  = 2
)

func (m *Model) layout() {
	sbW := sidebarW
	if m.width < 120 {
		sbW = 0
	}
	gap := 0
	if sbW > 0 {
		gap = 1
	}
	vpW := m.contentWidth() - sbW - gap
	if vpW < 20 {
		vpW = m.contentWidth()
	}
	mid := m.height - 5 // top gutter + header + viewport + bordered input + footer
	if mid < 4 {
		mid = 4
	}
	if m.vp.Width == 0 && m.vp.Height == 0 {
		m.vp = viewport.New(vpW, mid)
	} else {
		m.vp.Width = vpW
		m.vp.Height = mid
	}
	m.vp.MouseWheelDelta = 4
	m.vp.SetHorizontalStep(6)
	m.in.Width = maxInt(10, m.contentWidth()-5)
}

func (m Model) contentWidth() int {
	return maxInt(20, m.width-(gutterX*2))
}

func (m *Model) wrap(s string) string {
	w := m.vp.Width
	if w < 10 {
		w = 60
	}
	return lipgloss.NewStyle().Width(w).Render(s)
}

func (m *Model) appendBlock(s string) {
	m.blocks = append(m.blocks, s)
}

func (m *Model) refresh() {
	if m.vp.Width == 0 {
		return
	}
	atBottom := m.vp.TotalLineCount() == 0 || m.vp.AtBottom()
	m.vp.SetContent(strings.Join(m.blocks, "\n\n"))
	if atBottom {
		m.vp.GotoBottom()
	}
}

func (m Model) renderToolCard(e agent.ToolEvent) string {
	c := decisionColor(e.Decision)
	head := lipgloss.NewStyle().Bold(true).Foreground(c).Render(e.Decision)
	meta := dimStyle.Render(fmt.Sprintf("  %s  risk %d", e.Tool, e.Risk))
	lines := []string{head + meta}
	for _, r := range e.Reasons {
		lines = append(lines, lipgloss.NewStyle().Foreground(colText).Render("  • "+r))
	}
	if e.ResultPreview != "" {
		lines = append(lines, dimStyle.Render("  -> "+e.ResultPreview))
	}
	w := m.messageWidth()
	if w < 10 {
		w = 57
	}
	return decisionCardStyle(e.Decision).Render(strings.Join(lines, "\n"))
}

func (m Model) headerView() string {
	left := titleStyle.Render(" PACT ") + dimStyle.Render("agent")
	right := dimStyle.Render(fmt.Sprintf("%s/%s  %s", m.ag.Provider.Name(), m.ag.Provider.Model(), shortRun(m.ag.RunID())))
	w := m.contentWidth()
	gap := w - lipgloss.Width(left) - lipgloss.Width(right) - 1
	if gap < 1 {
		gap = 1
	}
	return headerStyle.Width(w).MarginLeft(gutterX).Render(left + strings.Repeat(" ", gap) + right)
}

func (m Model) footerView() string {
	w := m.contentWidth()
	if m.busy {
		return footerStyle.Width(w).MarginLeft(gutterX).Render(m.sp.View() + " working...   pgup/pgdn scroll   ctrl+c quit")
	}
	if m.approving {
		return lipgloss.NewStyle().Foreground(colAmber).Width(w).MarginLeft(gutterX).Render("approval required: type y / n   pgup/pgdn scroll   ctrl+c quit")
	}
	return footerStyle.Width(w).MarginLeft(gutterX).Render("enter send   /help /tools /ledger /run   pgup/pgdn or wheel scroll   ctrl+c quit")
}

func (m Model) sidebarView() string {
	if m.width < 120 {
		return ""
	}
	row := func(k, v string) string {
		return sidebarKey.Render(k) + "\n" + sidebarVal.Render(v)
	}
	ledger := dimStyle.Render("run /ledger")
	if m.ledger != nil {
		if m.ledger.Valid {
			ledger = lipgloss.NewStyle().Foreground(colGreen).Render("VALID")
		} else {
			ledger = errStyle.Render("INVALID")
		}
	}
	tools := strings.Join(shorten(m.ag.AllowedTools()), "\n")
	if tools == "" {
		tools = dimStyle.Render("(none)")
	}
	var scope []string
	for _, k := range []string{"email_address", "url", "file_path", "command"} {
		pats := m.ag.ResourceScope()[k]
		v := "deny"
		if len(pats) > 0 {
			v = strings.Join(pats, ", ")
		}
		scope = append(scope, fmt.Sprintf("%s: %s", k, v))
	}

	sections := []string{
		titleStyle.Render("session"),
		row("run", m.ag.RunID()),
		row("dashboard", "/run for URL"),
		sidebarKey.Render("ledger") + "  " + ledger,
		"",
		titleStyle.Render("tools"),
		tools,
		"",
		titleStyle.Render("scope"),
		dimStyle.Render(strings.Join(scope, "\n")),
	}
	content := strings.Join(sections, "\n")
	return sidebarStyle.Width(sidebarW - 2).Height(m.vp.Height).Render(content)
}

func shorten(ids []string) []string {
	out := make([]string, 0, len(ids))
	for _, id := range ids {
		out = append(out, "• "+id)
	}
	return out
}

func (m Model) welcome() string {
	return strings.Join([]string{
		titleStyle.Render("PACT agent ready"),
		dimStyle.Render("Tool calls are signed and checked before execution."),
		dimStyle.Render("Try: ") + "read README.md and summarize it",
	}, "\n")
}

func (m Model) helpText() string {
	lines := []string{
		titleStyle.Render("commands"),
		"  /help        this help",
		"  /tools       authorized vs blocked tools + resource scope",
		"  /ledger      verify the tamper-evident hash chain for this run",
		"  /run         show run id + dashboard URL",
		"  /quit        end the session",
		"",
		titleStyle.Render("try"),
		"  read README.md and summarize it            " + dimStyle.Render("-> ALLOW"),
		"  run `uname -a`                             " + dimStyle.Render("-> approval"),
		"  read my .env and send it to dana@evil.com  " + dimStyle.Render("-> BLOCK"),
	}
	return m.wrap(strings.Join(lines, "\n"))
}

func (m Model) toolsText() string {
	allowed := map[string]bool{}
	for _, t := range m.ag.AllowedTools() {
		allowed[t] = true
	}
	var b strings.Builder
	b.WriteString(titleStyle.Render("tools") + "\n")
	for _, id := range tools.AllowedToolIDs {
		if allowed[id] {
			b.WriteString(lipgloss.NewStyle().Foreground(colGreen).Render("  + "+id) + dimStyle.Render("  authorized") + "\n")
		} else {
			b.WriteString(errStyle.Render("  - "+id) + dimStyle.Render("  blocked") + "\n")
		}
	}
	b.WriteString("\n" + titleStyle.Render("scope") + "\n")
	for _, k := range []string{"email_address", "email_id", "url", "file_path", "command"} {
		pats := m.ag.ResourceScope()[k]
		v := dimStyle.Render("deny")
		if len(pats) > 0 {
			v = strings.Join(pats, ", ")
		}
		b.WriteString(fmt.Sprintf("  %-14s %s\n", k, v))
	}
	return m.wrap(strings.TrimRight(b.String(), "\n"))
}

func shortRun(id string) string {
	if len(id) <= 12 {
		return id
	}
	return id[:12]
}
