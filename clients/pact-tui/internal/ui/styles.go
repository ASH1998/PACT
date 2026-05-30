package ui

import "github.com/charmbracelet/lipgloss"

var (
	colBg      = lipgloss.Color("#1e1e2e")
	colPanel   = lipgloss.Color("#242438")
	colSurface = lipgloss.Color("#313244")
	colLine    = lipgloss.Color("#45475a")
	colGreen   = lipgloss.Color("#a6e3a1")
	colCyan    = lipgloss.Color("#94e2d5")
	colIndigo  = lipgloss.Color("#b4befe")
	colRed     = lipgloss.Color("#f38ba8")
	colAmber   = lipgloss.Color("#fab387")
	colBlue    = lipgloss.Color("#89b4fa")
	colPurple  = lipgloss.Color("#cba6f7")
	colDim     = lipgloss.Color("#6c7086")
	colSubtle  = lipgloss.Color("#a6adc8")
	colText    = lipgloss.Color("#cdd6f4")
	colCodeBg  = lipgloss.Color("#181825")
	colCodeDim = lipgloss.Color("#9399b2")

	appStyle = lipgloss.NewStyle().Foreground(colText)

	titleStyle = lipgloss.NewStyle().Bold(true).Foreground(colAmber)
	dimStyle   = lipgloss.NewStyle().Foreground(colDim)

	youStyle   = lipgloss.NewStyle().Bold(true).Foreground(colBlue)
	agentStyle = lipgloss.NewStyle().Bold(true).Foreground(colAmber)
	errStyle   = lipgloss.NewStyle().Foreground(colRed).Bold(true)
	sysStyle   = lipgloss.NewStyle().Foreground(colDim).Italic(true)

	chatStyle = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder(), false, false, false, true).
			BorderForeground(colLine).
			MarginTop(1).
			Padding(0, 2)

	sidebarStyle = lipgloss.NewStyle().
			Border(lipgloss.NormalBorder(), false, false, false, true).
			BorderForeground(colLine).
			Foreground(colSubtle).
			Padding(0, 1)

	sidebarKey = lipgloss.NewStyle().Foreground(colDim)
	sidebarVal = lipgloss.NewStyle().Foreground(colText)

	footerStyle = lipgloss.NewStyle().Foreground(colDim)
	headerStyle = lipgloss.NewStyle().Bold(true).Foreground(colText)
	inputStyle  = lipgloss.NewStyle().Border(lipgloss.NormalBorder(), true, false, false, false).BorderForeground(colLine).PaddingLeft(1)
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
		MarginTop(1).
		Padding(0, 2)
}
