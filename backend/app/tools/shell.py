"""Mock shell tool."""


def shell_execute_mock(command: str = "echo hello", **kwargs) -> dict:
    """Mock shell execution."""
    return {
        "type": "shell_output",
        "command": command,
        "exit_code": 0,
        "stdout": f"[MOCK] Executed: {command}",
        "stderr": "",
    }
