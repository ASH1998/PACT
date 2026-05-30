package ui

import (
	"regexp"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/x/ansi"
)

var (
	inlineCodeStyle = lipgloss.NewStyle().Foreground(colAmber)
	codeBlockStyle  = lipgloss.NewStyle().Foreground(colText)
	codeFenceStyle  = lipgloss.NewStyle().Foreground(colPurple)
	quoteStyle      = lipgloss.NewStyle().Foreground(colSubtle).Border(lipgloss.NormalBorder(), false, false, false, true).BorderForeground(colLine).PaddingLeft(1)
	headingStyles   = []lipgloss.Style{
		lipgloss.NewStyle().Bold(true).Foreground(colAmber),
		lipgloss.NewStyle().Bold(true).Foreground(colBlue),
		lipgloss.NewStyle().Bold(true).Foreground(colPurple),
	}
	linkRE = regexp.MustCompile(`\[([^\]]+)\]\(([^)]+)\)`)
)

func (m Model) renderUser(text string) string {
	bodyW := m.messageWidth()
	body := lipgloss.NewStyle().Foreground(colText).Render(wrapText(renderInline(text), bodyW))
	return chatStyle.BorderForeground(colBlue).Render(
		youStyle.Render("user") + "\n" + body,
	)
}

func (m Model) renderAgent(text string) string {
	bodyW := m.messageWidth()
	body := renderMarkdown(text, bodyW)
	return chatStyle.BorderForeground(colAmber).Render(
		agentStyle.Render("assistant") + "\n" + body,
	)
}

func (m Model) messageWidth() int {
	w := m.vp.Width - 10
	if w < 40 {
		w = maxInt(20, m.vp.Width-8)
	}
	return w
}

func renderMarkdown(md string, width int) string {
	md = strings.ReplaceAll(md, "\r\n", "\n")
	lines := strings.Split(md, "\n")
	out := make([]string, 0, len(lines))

	for i := 0; i < len(lines); i++ {
		line := lines[i]
		trim := strings.TrimSpace(line)
		if trim == "" {
			if len(out) > 0 && out[len(out)-1] != "" {
				out = append(out, "")
			}
			continue
		}

		if fence, lang, ok := parseFence(trim); ok {
			var code []string
			for i++; i < len(lines); i++ {
				if strings.HasPrefix(strings.TrimSpace(lines[i]), fence) {
					break
				}
				code = append(code, lines[i])
			}
			out = append(out, renderCodeBlock(lang, code, width))
			continue
		}

		if level, text, ok := parseHeading(trim); ok {
			idx := minInt(level-1, len(headingStyles)-1)
			out = append(out, headingStyles[idx].Render(wrapText(renderInline(text), width)))
			continue
		}

		if isRule(trim) {
			out = append(out, dimStyle.Render(strings.Repeat("-", minInt(maxInt(8, width), 72))))
			continue
		}

		if strings.HasPrefix(trim, ">") {
			quote := strings.TrimSpace(strings.TrimLeft(trim, ">"))
			out = append(out, quoteStyle.Render(wrapText(renderInline(quote), maxInt(10, width-2))))
			continue
		}

		if bullet, text, ok := parseList(trim); ok {
			item := wrapText(renderInline(text), maxInt(8, width-4))
			out = append(out, dimStyle.Render(bullet+" ")+item)
			continue
		}

		paragraph := []string{trim}
		for i+1 < len(lines) {
			next := strings.TrimSpace(lines[i+1])
			if next == "" || startsBlock(next) {
				break
			}
			i++
			paragraph = append(paragraph, next)
		}
		out = append(out, wrapText(renderInline(strings.Join(paragraph, " ")), width))
	}

	return strings.TrimRight(strings.Join(out, "\n"), "\n")
}

func parseFence(line string) (fence string, lang string, ok bool) {
	for _, marker := range []string{"```", "~~~"} {
		if strings.HasPrefix(line, marker) {
			return marker, strings.TrimSpace(strings.TrimPrefix(line, marker)), true
		}
	}
	return "", "", false
}

func parseHeading(line string) (level int, text string, ok bool) {
	if !strings.HasPrefix(line, "#") {
		return 0, "", false
	}
	for level < len(line) && line[level] == '#' {
		level++
	}
	if level == 0 || level > 6 || level >= len(line) || line[level] != ' ' {
		return 0, "", false
	}
	return level, strings.TrimSpace(line[level:]), true
}

func parseList(line string) (bullet string, text string, ok bool) {
	if len(line) >= 2 && (strings.HasPrefix(line, "- ") || strings.HasPrefix(line, "* ") || strings.HasPrefix(line, "+ ")) {
		return "•", strings.TrimSpace(line[2:]), true
	}
	for i, r := range line {
		if r == '.' && i > 0 && i+1 < len(line) && line[i+1] == ' ' {
			allDigits := true
			for _, d := range line[:i] {
				if d < '0' || d > '9' {
					allDigits = false
					break
				}
			}
			if allDigits {
				return line[:i+1], strings.TrimSpace(line[i+2:]), true
			}
		}
	}
	return "", "", false
}

func startsBlock(line string) bool {
	if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, ">") || isRule(line) {
		return true
	}
	if _, _, ok := parseFence(line); ok {
		return true
	}
	if _, _, ok := parseList(line); ok {
		return true
	}
	return false
}

func isRule(line string) bool {
	if len(line) < 3 {
		return false
	}
	for _, r := range line {
		if r != '-' && r != '*' && r != '_' {
			return false
		}
	}
	return true
}

func renderCodeBlock(lang string, code []string, width int) string {
	if len(code) == 0 {
		code = []string{""}
	}
	innerW := maxInt(12, width-4)
	label := "code"
	if lang != "" {
		label = strings.ToLower(lang)
	}
	out := []string{codeFenceStyle.Render(label)}
	for _, line := range code {
		line = strings.ReplaceAll(strings.TrimRight(line, " \t"), "\t", "    ")
		out = append(out, codeBlockStyle.Render(wrapText(highlightCodeLine(line), innerW)))
	}
	return lipgloss.NewStyle().
		MarginTop(1).
		MarginBottom(1).
		Border(lipgloss.NormalBorder(), false, false, false, true).
		BorderForeground(colLine).
		PaddingLeft(1).
		Render(strings.Join(out, "\n"))
}

func highlightCodeLine(line string) string {
	trim := strings.TrimSpace(line)
	switch {
	case strings.HasPrefix(trim, "//"), strings.HasPrefix(trim, "#"), strings.HasPrefix(trim, "--"):
		return lipgloss.NewStyle().Foreground(colCodeDim).Render(line)
	case strings.HasPrefix(trim, "+"):
		return lipgloss.NewStyle().Foreground(colGreen).Render(line)
	case strings.HasPrefix(trim, "-"):
		return lipgloss.NewStyle().Foreground(colRed).Render(line)
	default:
		return line
	}
}

func renderInline(s string) string {
	s = linkRE.ReplaceAllString(s, "$1 ($2)")
	var b strings.Builder
	for len(s) > 0 {
		codeStart := strings.Index(s, "`")
		boldStart := strings.Index(s, "**")
		next := nextInline(codeStart, boldStart)
		if next < 0 {
			b.WriteString(s)
			break
		}
		b.WriteString(s[:next])
		s = s[next:]
		if strings.HasPrefix(s, "`") {
			end := strings.Index(s[1:], "`")
			if end < 0 {
				b.WriteString(s)
				break
			}
			b.WriteString(inlineCodeStyle.Render(s[1 : end+1]))
			s = s[end+2:]
			continue
		}
		if strings.HasPrefix(s, "**") {
			end := strings.Index(s[2:], "**")
			if end < 0 {
				b.WriteString(s)
				break
			}
			b.WriteString(lipgloss.NewStyle().Bold(true).Foreground(colText).Render(s[2 : end+2]))
			s = s[end+4:]
			continue
		}
	}
	return b.String()
}

func nextInline(a, b int) int {
	if a < 0 {
		return b
	}
	if b < 0 || a < b {
		return a
	}
	return b
}

func wrapText(s string, width int) string {
	if width < 8 {
		width = 8
	}
	return strings.TrimRight(ansi.Wordwrap(s, width, " "), " ")
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
