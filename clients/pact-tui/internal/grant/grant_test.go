package grant

import "testing"

func TestLoadAcmeExample(t *testing.T) {
	g, err := Load("../../../../examples/grant.acme.yaml")
	if err != nil {
		t.Fatalf("load: %v", err)
	}
	if !g.AllTools {
		t.Errorf("expected tools: \"*\" -> AllTools true, got %v", g.Tools)
	}
	if got := g.ResourceScope["email_address"]; len(got) != 1 || got[0] != "*@acme.com" {
		t.Errorf("email_address scope = %v", got)
	}
	if got := g.ResourceScope["command"]; len(got) != 0 {
		t.Errorf("command scope should be empty (deny), got %v", got)
	}
}

func TestDefaultGrantDenyByDefault(t *testing.T) {
	g := Default()
	if g.AllTools {
		t.Error("default grant must not allow all tools")
	}
	if g.AllowsTool("email.send") {
		t.Error("default grant must not allow email.send")
	}
	if g.AllowsTool("shell.execute_mock") {
		t.Error("default grant must not allow shell")
	}
	if !g.AllowsTool("file.read") {
		t.Error("default grant should allow file.read")
	}
	ceiling := g.ToolCeiling([]string{"file.read", "email.send", "shell.execute_mock", "web.read"})
	if len(ceiling) != 2 {
		t.Errorf("ceiling = %v, want [file.read web.read]", ceiling)
	}
}
