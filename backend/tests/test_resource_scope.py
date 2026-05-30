"""Unit tests for the resource-scope matcher (app.tools.resource.resource_in_scope).

The matcher is the authority boundary for *which resources* a tool may touch.
It is strict per-type: an empty/missing pattern list for a scoped resource type
denies; "*" allows all; tools with no meaningful resource are always in scope.
"""

from app.tools.resource import resource_in_scope


def test_default_resource_type_always_in_scope():
    # summarize / respond_to_user have resource_type "default"
    assert resource_in_scope("default", "anything", {}) is True


def test_missing_or_empty_patterns_deny():
    assert resource_in_scope("email_address", "a@b.com", {}) is False
    assert resource_in_scope("email_address", "a@b.com", {"email_address": []}) is False
    assert resource_in_scope("command", "ls", {"command": []}) is False


def test_wildcard_allows_all():
    assert resource_in_scope("url", "https://anything.example", {"url": ["*"]}) is True
    assert resource_in_scope("file_path", "/etc/shadow", {"file_path": ["*"]}) is True


def test_email_domain_wildcard():
    scope = {"email_address": ["*@acme.com"]}
    assert resource_in_scope("email_address", "bob@acme.com", scope) is True
    assert resource_in_scope("email_address", "BOB@ACME.COM", scope) is True
    assert resource_in_scope("email_address", "attacker@evil.com", scope) is False
    # missing "to" arg falls back to "default" → not an acme address → deny
    assert resource_in_scope("email_address", "default", scope) is False


def test_email_exact_match():
    scope = {"email_address": ["alerts@acme.com"]}
    assert resource_in_scope("email_address", "alerts@acme.com", scope) is True
    assert resource_in_scope("email_address", "bob@acme.com", scope) is False


def test_url_host_matching():
    scope = {"url": ["*.acme.com", "docs.python.org"]}
    assert resource_in_scope("url", "https://wiki.acme.com/x", scope) is True
    assert resource_in_scope("url", "https://acme.com", scope) is True
    assert resource_in_scope("url", "https://docs.python.org/3/", scope) is True
    assert resource_in_scope("url", "https://evil.com/acme.com", scope) is False
    assert resource_in_scope("url", "http://attacker.io", scope) is False


def test_file_path_glob():
    scope = {"file_path": ["*.md", "src/*"]}
    assert resource_in_scope("file_path", "README.md", scope) is True
    assert resource_in_scope("file_path", "src/app.py", scope) is True
    assert resource_in_scope("file_path", ".env", scope) is False
    assert resource_in_scope("file_path", "secrets/key.pem", scope) is False
