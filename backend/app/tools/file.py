"""Mock file tool."""


def file_read(path: str = "documents/report.txt", **kwargs) -> dict:
    """Read a mock non-secret file."""
    from app.tools.seed_data import SEED_DATA

    return SEED_DATA.get("safe_internal_file", {
        "type": "file_content",
        "path": path,
        "content": "Quarterly report: Revenue up 15%. No action required.",
        "size_bytes": 1024,
    })


def file_read_secret(path: str = ".env", **kwargs) -> dict:
    """Read a mock secret file."""
    from app.tools.seed_data import SEED_DATA

    return SEED_DATA["mock_env_file"]
