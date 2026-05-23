"""Tests for provenance service."""

import pytest
from app.services.provenance import ProvenanceService


@pytest.fixture
def provenance_service():
    return ProvenanceService()


def test_email_read_labeled_untrusted(provenance_service):
    """email.read produces an untrusted.email output label."""
    run_id = "run_prov_email"
    provenance_service.start_run(run_id)
    provenance_service.record_step(run_id, "email.read")
    prov = provenance_service.build_provenance(run_id, "email.read")

    assert "untrusted.email" in prov["influenced_by"]
    assert "untrusted.email" in prov["uses_data"]


def test_secret_file_labeled_secret(provenance_service):
    """file.read_secret produces a secret label."""
    run_id = "run_prov_secret"
    provenance_service.start_run(run_id)
    provenance_service.record_step(run_id, "file.read_secret")
    prov = provenance_service.build_provenance(run_id, "file.read_secret")

    assert "secret" in prov["influenced_by"]
    assert "secret" in prov["uses_data"]


def test_send_email_labeled_external_write(provenance_service):
    """email.send has an external_write side_effect."""
    run_id = "run_prov_send"
    provenance_service.start_run(run_id)
    provenance_service.record_step(run_id, "email.send")
    prov = provenance_service.build_provenance(run_id, "email.send")

    assert prov["side_effect"] == "external_write"


def test_propagate_combines_labels(provenance_service):
    """Multiple steps accumulate labels in influenced_by."""
    run_id = "run_prov_combine"
    provenance_service.start_run(run_id)

    # Step 1: email.read
    provenance_service.record_step(run_id, "email.read")
    prov1 = provenance_service.build_provenance(run_id, "email.read")
    assert "untrusted.email" in prov1["influenced_by"]

    # Step 2: file.read_secret
    provenance_service.record_step(run_id, "file.read_secret")
    prov2 = provenance_service.build_provenance(run_id, "file.read_secret")
    # Should include both the initial trusted.user, untrusted.email from step 1,
    # and secret from step 2
    assert "trusted.user" in prov2["influenced_by"]
    assert "untrusted.email" in prov2["influenced_by"]
    assert "secret" in prov2["influenced_by"]
