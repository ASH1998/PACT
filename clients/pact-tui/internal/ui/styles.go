package ui

import "github.com/charmbracelet/lipgloss"

var (
	colGreen  = lipgloss.Color("#34d399")
	colCyan   = lipgloss.Color("#22d3ee")
	colIndigo = lipgloss.Color("#818cf8")
	colRed    = lipgloss.Color("#f87171")
	colAmber  = lipgloss.Color("#fbbf24")
	colDim    = lipgloss.Color("#64748b")
	colText   = lipgloss.Color("#e2e8f0")

	titleStyle = lipgloss.NewStyle().Bold(true).Foreground(colCyan)
	dimStyle   = lipgloss.NewStyle().Foreground(colDim)

	youStyle   = lipgloss.NewStyle().Bold(true).Foreground(colText)
	agentStyle = lipgloss.NewStyle().Foreground(colCyan)
	errStyle   = lipgloss.NewStyle().Foreground(colRed).Bold(true)
	sysStyle   = lipgloss.NewStyle().Foreground(colDim).Italic(true)

	sidebarStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(colIndigo).
			Padding(0, 1)

	sidebarKey = lipgloss.NewStyle().Foreground(colDim)
	sidebarVal = lipgloss.NewStyle().Foreground(colText)

	footerStyle = lipgloss.NewStyle().Foreground(colDim)
	headerStyle = lipgloss.NewStyle().Bold(true).Foreground(colIndigo)
)

// decisionStyle returns the accent color for a PACT decision.
func decisionColor(decision string) lipgloss.Color {
	switch decision {
	case "ALLOW":
		return colGreen
	case "REQUIRE_APPROVAL":
		return colAmber
	default:
		return colRed
	}
}

func decisionCardStyle(decision string) lipgloss.Style {
	c := decisionColor(decision)
	return lipgloss.NewStyle().
		Border(lipgloss.NormalBorder(), false, false, false, true).
		BorderForeground(c).
		PaddingLeft(1)
}
