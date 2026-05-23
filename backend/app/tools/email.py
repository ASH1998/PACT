"""Mock email tool."""


def email_read(email_id: str = "latest", **kwargs) -> dict:
    """Read a mock email."""
    from app.tools.seed_data import SEED_DATA

    if email_id == "latest":
        return SEED_DATA["normal_invoice_email"]
    return SEED_DATA.get(email_id, {"error": "Email not found"})


def email_send(to: str, subject: str = "", body: str = "", **kwargs) -> dict:
    """Mock email send — always returns success (policy should block before this)."""
    return {
        "type": "email_sent",
        "to": to,
        "subject": subject,
        "status": "sent",
    }
