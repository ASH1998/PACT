// Package ui implements the Bubble Tea terminal UI for the PACT agent console.
package ui

import (
	"context"
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"

	"pacttui/internal/agent"
	"pacttui/internal/pact"
)

type setupDoneMsg struct{ err error }
type eventMsg struct{ ev agent.Event }
type ledgerMsg struct {
	l   pact.Ledger
	err error
}

// Model is the root Bubble Tea model.
type Model struct {
	ag            *agent.Agent
	dashboardBase string

	vp viewport.Model
	in textinput.Model
	sp spinner.Model

	width, height int
	ready         bool
	busy          bool
	approving     bool
	setupErr      error

	blocks  []string
	eventCh chan agent.Event
	ledger  *pact.Ledger
}

// New builds the UI model for an (un-set-up) agent.
func New(ag *agent.Agent, dashboardBase string) Model {
	ti := textinput.New()
	ti.Placeholder = "Ask PACT..."
	ti.Prompt = ">"
	ti.CharLimit = 4000
	ti.PromptStyle = youStyle
	ti.TextStyle = lipgloss.NewStyle().Foreground(colText)
	ti.PlaceholderStyle = dimStyle
	ti.Cursor.Style = lipgloss.NewStyle().Foreground(colAmber)

	sp := spinner.New()
	sp.Spinner = spinner.Dot
	sp.Style = lipgloss.NewStyle().Foreground(colCyan)

	return Model{ag: ag, dashboardBase: strings.TrimRight(dashboardBase, "/"), in: ti, sp: sp}
}

// Init starts setup and the spinner.
func (m Model) Init() tea.Cmd {
	return tea.Batch(m.sp.Tick, m.setupCmd())
}

func (m Model) setupCmd() tea.Cmd {
	return func() tea.Msg {
		return setupDoneMsg{err: m.ag.Setup(context.Background())}
	}
}

func waitEvent(ch chan agent.Event) tea.Cmd {
	return func() tea.Msg { return eventMsg{ev: <-ch} }
}

func (m Model) ledgerCmd() tea.Cmd {
	return func() tea.Msg {
		l, err := m.ag.VerifyLedger(context.Background())
		return ledgerMsg{l: l, err: err}
	}
}

// Update handles messages.
func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height
		m.layout()
		m.ready = true
		m.refresh()
		return m, nil

	case spinner.TickMsg:
		if m.busy {
			var cmd tea.Cmd
			m.sp, cmd = m.sp.Update(msg)
			return m, cmd
		}
		return m, nil

	case setupDoneMsg:
		if msg.err != nil {
			m.setupErr = msg.err
			m.busy = false
			m.appendBlock(errStyle.Render("setup failed: ") + msg.err.Error())
			m.refresh()
			return m, nil
		}
		m.in.Focus()
		m.appendBlock(m.welcome())
		m.refresh()
		return m, textinput.Blink

	case ledgerMsg:
		if msg.err != nil {
			m.appendBlock(errStyle.Render("ledger error: ") + msg.err.Error())
		} else {
			m.ledger = &msg.l
			status := lipgloss.NewStyle().Foreground(colGreen).Render("VALID")
			if !msg.l.Valid {
				status = errStyle.Render("INVALID")
			}
			line := fmt.Sprintf("%s ledger %s", sysStyle.Render("/ledger ->"), status)
			if len(msg.l.Issues) > 0 {
				line += "\n" + dimStyle.Render("  "+strings.Join(msg.l.Issues, "\n  "))
			}
			m.appendBlock(line)
		}
		m.refresh()
		return m, nil

	case eventMsg:
		return m.handleEvent(msg.ev)

	case tea.KeyMsg:
		return m.handleKey(msg)

	case tea.MouseMsg:
		if m.ready {
			var cmd tea.Cmd
			m.vp, cmd = m.vp.Update(msg)
			return m, cmd
		}
	}

	// Forward to input when interactive.
	if m.ready && !m.busy {
		var cmd tea.Cmd
		m.in, cmd = m.in.Update(msg)
		return m, cmd
	}
	return m, nil
}

func (m Model) handleKey(msg tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch msg.String() {
	case "ctrl+c", "esc":
		return m, tea.Sequence(
			func() tea.Msg { _ = m.ag.Complete(context.Background()); return nil },
			tea.Quit,
		)
	case "pgup", "pgdown", "ctrl+u", "ctrl+d":
		var cmd tea.Cmd
		m.vp, cmd = m.vp.Update(msg)
		return m, cmd
	case "alt+up":
		m.vp.ScrollUp(1)
		return m, nil
	case "alt+down":
		m.vp.ScrollDown(1)
		return m, nil
	}

	if m.busy {
		return m, nil
	}

	if msg.Type == tea.KeyEnter {
		val := strings.TrimSpace(m.in.Value())
		if val == "" {
			return m, nil
		}
		m.in.Reset()
		if m.approving {
			return m.resolveApproval(val)
		}
		if strings.HasPrefix(val, "/") {
			return m.handleCommand(val)
		}
		return m.startTurn(val)
	}

	var cmd tea.Cmd
	m.in, cmd = m.in.Update(msg)
	return m, cmd
}

func (m Model) startTurn(text string) (tea.Model, tea.Cmd) {
	m.appendBlock(m.renderUser(text))
	m.busy = true
	m.eventCh = make(chan agent.Event, 64)
	ch := m.eventCh
	go m.ag.Turn(context.Background(), text, func(ev agent.Event) { ch <- ev })
	m.refresh()
	return m, tea.Batch(waitEvent(ch), m.sp.Tick)
}

func (m Model) resolveApproval(val string) (tea.Model, tea.Cmd) {
	low := strings.ToLower(val)
	yes := low == "y" || low == "yes" || low == "approve" || low == "approved"
	no := low == "n" || low == "no" || low == "deny" || low == "denied"
	if !yes && !no {
		m.appendBlock(sysStyle.Render("Type y to approve or n to deny."))
		m.refresh()
		return m, nil
	}
	m.approving = false
	m.in.Placeholder = "Ask PACT..."
	m.busy = true
	verb := "approved"
	if no {
		verb = "denied"
	}
	m.appendBlock(sysStyle.Render("you " + verb + " the pending action"))
	m.eventCh = make(chan agent.Event, 64)
	ch := m.eventCh
	go m.ag.Resume(context.Background(), yes, func(ev agent.Event) { ch <- ev })
	m.refresh()
	return m, tea.Batch(waitEvent(ch), m.sp.Tick)
}

func (m Model) handleEvent(ev agent.Event) (tea.Model, tea.Cmd) {
	switch e := ev.(type) {
	case agent.AgentText:
		m.appendBlock(m.renderAgent(e.Text))
		m.refresh()
		return m, waitEvent(m.eventCh)
	case agent.ToolEvent:
		m.appendBlock(m.renderToolCard(e))
		m.refresh()
		return m, waitEvent(m.eventCh)
	case agent.ApprovalNeeded:
		m.approving = true
		m.busy = false
		m.in.Placeholder = "approve? (y / n)"
		m.appendBlock(lipgloss.NewStyle().Foreground(colAmber).Bold(true).
			Render("! PACT requires approval for: "+strings.Join(e.Tools, ", ")) +
			"\n" + dimStyle.Render("  type y to approve or n to deny"))
		m.refresh()
		return m, nil
	case agent.Done:
		m.busy = false
		m.refresh()
		return m, nil
	case agent.Err:
		m.busy = false
		m.appendBlock(errStyle.Render("error: ") + e.Error.Error())
		m.refresh()
		return m, nil
	}
	return m, nil
}

func (m Model) handleCommand(cmd string) (tea.Model, tea.Cmd) {
	fields := strings.Fields(cmd)
	if len(fields) == 0 {
		return m, nil
	}
	switch fields[0] {
	case "/quit", "/exit":
		return m, tea.Sequence(
			func() tea.Msg { _ = m.ag.Complete(context.Background()); return nil },
			tea.Quit,
		)
	case "/help":
		m.appendBlock(m.helpText())
	case "/tools", "/grant":
		m.appendBlock(m.toolsText())
	case "/run":
		m.appendBlock(sysStyle.Render("run ") + m.ag.RunID() + "\n" +
			dimStyle.Render(m.dashboardBase+"/runs/"+m.ag.RunID()))
	case "/ledger":
		m.appendBlock(sysStyle.Render("verifying ledger..."))
		m.refresh()
		return m, m.ledgerCmd()
	default:
		m.appendBlock(sysStyle.Render("unknown command: " + cmd + "  (try /help)"))
	}
	m.refresh()
	return m, nil
}

// View renders the UI.
func (m Model) View() string {
	if !m.ready {
		return "\n  " + m.sp.View() + " starting PACT agent console..."
	}
	header := m.headerView()
	sidebar := m.sidebarView()
	body := lipgloss.NewStyle().MarginLeft(gutterX).Render(m.vp.View())
	if sidebar != "" {
		body = lipgloss.JoinHorizontal(lipgloss.Top, body, " ", sidebar)
	}
	input := inputStyle.Width(m.contentWidth()).MarginLeft(gutterX).Render(m.in.View())
	return appStyle.Width(m.width).Render(strings.Join([]string{"", header, body, input, m.footerView()}, "\n"))
}
