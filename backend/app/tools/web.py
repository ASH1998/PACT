"""Mock web tool."""


def web_read(url: str = "https://example.com", **kwargs) -> dict:
    """Read mock web content."""
    from app.tools.seed_data import SEED_DATA

    if "malicious" in url.lower():
        return SEED_DATA["malicious_webpage"]
    return {
        "type": "web_content",
        "url": url,
        "title": "Example Page",
        "content": "This is a normal webpage with useful information about invoices and billing.",
        "links": [],
    }
