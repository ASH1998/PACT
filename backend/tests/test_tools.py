"""Tests for mock tools."""

from app.tools import get_mock_tool, list_tools


class TestToolRegistry:
    def test_all_tools_registered(self):
        expected = [
            "email.read", "email.send", "web.read",
            "file.read", "file.read_secret", "shell.execute_mock", "respond_to_user",
        ]
        registered = list_tools()
        for name in expected:
            assert name in registered, f"Tool {name} not registered"

    def test_get_mock_tool_unknown_returns_none(self):
        result = get_mock_tool("nonexistent.tool")
        assert result is None


class TestEmailTool:
    def test_email_read_normal(self):
        tool = get_mock_tool("email.read")
        assert tool is not None
        result = tool(email_id="normal_invoice")
        assert isinstance(result, dict)
        assert "Invoice" in result.get("subject", result.get("body", ""))

    def test_email_read_malicious(self):
        tool = get_mock_tool("email.read")
        result = tool(email_id="malicious_invoice")
        assert isinstance(result, dict)

    def test_email_send(self):
        tool = get_mock_tool("email.send")
        result = tool(to="test@example.com", body="hello")
        assert result["type"] == "email_sent"
        assert result["to"] == "test@example.com"


class TestFileTool:
    def test_file_read_normal(self):
        tool = get_mock_tool("file.read")
        result = tool(path="/home/user/report.txt")
        assert isinstance(result, dict)

    def test_file_read_secret(self):
        tool = get_mock_tool("file.read_secret")
        result = tool(path="/home/user/.env")
        assert isinstance(result, dict)


class TestWebTool:
    def test_web_read(self):
        tool = get_mock_tool("web.read")
        result = tool(url="https://example.com/research")
        assert isinstance(result, dict)


class TestShellTool:
    def test_shell_execute(self):
        tool = get_mock_tool("shell.execute_mock")
        result = tool(command="ls -la")
        assert isinstance(result, dict)
