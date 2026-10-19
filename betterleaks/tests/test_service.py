"""Tests for Betterleaks-Presidio service."""
import pytest
from fastapi.testclient import TestClient

from app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "betterleaks-presidio"


def test_analyze_secret(client):
    payload = {
        "text": "My github token is ghp_123456789012345678901234567890123456",  # gitleaks:allow
        "language": "en",
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    results = response.json()
    assert len(results) > 0
    entity_types = [r["entity_type"] for r in results]
    assert "GITHUB_PAT" in entity_types


def test_analyze_custom_secret(client):
    payload = {
        "text": "Vault token: hvs.CAESIJL8k2jKlq0Pq1zWmNoPqRstUvwXyZaBcDeFgHiJkLmNoPqRs",  # gitleaks:allow
        "language": "en",
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    results = response.json()
    entity_types = [r["entity_type"] for r in results]
    assert "VAULT_TOKEN" in entity_types


def test_redact_replace_mode(client):
    payload = {
        "text": "Contact Alice at alice@example.com or use key ghp_123456789012345678901234567890123456",  # gitleaks:allow
        "mode": "replace",
    }
    response = client.post("/redact", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_secrets"] is True
    assert "<GITHUB_PAT>" in data["clean_text"]
    assert "<EMAIL_ADDRESS>" in data["clean_text"]
    assert "ghp_" not in data["clean_text"]


def test_redact_mask_mode(client):
    payload = {
        "text": "Secret ghp_123456789012345678901234567890123456",  # gitleaks:allow
        "mode": "mask",
        "mask_char": "#",
    }
    response = client.post("/redact", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_secrets"] is True
    assert "########################################" in data["clean_text"]
    assert "ghp_" not in data["clean_text"]


def test_metrics(client):
    # Perform a redact request to generate metrics
    payload = {
        "text": "Secret ghp_123456789012345678901234567890123456",  # gitleaks:allow
        "mode": "replace",
    }
    client.post("/redact", json=payload)

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "betterleaks_scans_total" in response.text
    assert "betterleaks_findings_total" in response.text
    assert "betterleaks_scan_duration_seconds" in response.text


def test_redact_french_no_false_positive(client):
    text = (
        "2. **G\u00e9n\u00e8re un nouveau token** si tu en as besoin, et range-le dans une "
        "variable d'environnement (`HF_TOKEN`), jamais dans un fichier committ\u00e9 ni un chat."
    )
    payload = {"text": text, "mode": "replace"}
    response = client.post("/redact", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_secrets"] is False
    assert data["findings_count"] == 0
    assert data["clean_text"] == text


def test_redact_french_with_actual_secret(client):
    secret = "ghp_123456789012345678901234567890123456"  # gitleaks:allow
    text = (
        f"2. **G\u00e9n\u00e8re un nouveau token** si tu en as besoin: (`GITHUB_TOKEN`={secret}), "
        "jamais dans un fichier committ\u00e9 ni un chat."
    )
    payload = {"text": text, "mode": "replace"}
    response = client.post("/redact", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_secrets"] is True
    assert data["findings_count"] == 1
    assert "<GITHUB_PAT>" in data["clean_text"]
    assert secret not in data["clean_text"]
    assert "GITHUB_TOKEN" in data["clean_text"]


def test_tokenize_french_with_secret(client):
    secret = "ghp_123456789012345678901234567890123456"  # gitleaks:allow
    text = f"Token pour HuggingFace / GitHub: {secret} dans l'environnement (`HF_TOKEN`)"
    payload = {"text": text, "ttl_seconds": 60}
    response = client.post("/tokenize", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_secrets"] is True
    assert secret not in data["tokenized_text"]
    assert "HF_TOKEN" in data["tokenized_text"]


def test_redact_preserves_urls(client):
    text = (
        "1. **R\u00e9voquez ce token imm\u00e9diatement** : "
        "[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)"
    )
    payload = {"text": text, "mode": "replace"}
    response = client.post("/redact", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_secrets"] is False
    assert data["findings_count"] == 0
    assert data["clean_text"] == text
    assert "[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)" in data["clean_text"]


def test_redact_git_not_person(client):
    text = (
        "3. Si vous aviez ce token dans un repo Git, v\u00e9rifiez son historique "
        "(`git log` / GitHub secret scanning)"
    )
    # Test both French and English language modes
    for lang in ("fr", "en", "auto"):
        payload = {"text": text, "language": lang, "mode": "replace"}
        response = client.post("/redact", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["has_secrets"] is False
        assert data["findings_count"] == 0
        assert data["clean_text"] == text
        assert "<PERSON>" not in data["clean_text"]
        assert "repo Git" in data["clean_text"]


def test_redact_user_turn_with_secret_and_urls_and_git(client):
    secret = "ghp_123456789012345678901234567890123456"  # gitleaks:allow
    text = (
        f"1. **R\u00e9voquez ce token imm\u00e9diatement** : [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) \u2192 supprimez `{secret}`\n"
        "2. **G\u00e9n\u00e9rez un nouveau token** avec le minimum de droits n\u00e9cessaires (read-only si possible)\n"
        "3. Si vous aviez ce token dans un repo Git, v\u00e9rifiez son historique (`git log` / GitHub secret scanning)"
    )
    payload = {"text": text, "mode": "replace"}
    response = client.post("/redact", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_secrets"] is True
    assert data["findings_count"] == 1
    # URL is preserved intact
    assert "[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)" in data["clean_text"]
    # Secret is redacted
    assert "<GITHUB_PAT>" in data["clean_text"]
    assert secret not in data["clean_text"]
    # Git is preserved and NOT masked as <PERSON>
    assert "<PERSON>" not in data["clean_text"]
    assert "repo Git" in data["clean_text"]
    assert "`git log`" in data["clean_text"]


def test_redact_zero_width_space_evasion(client):
    """Test that zero-width characters (e.g. \\u200b, \\u200c, \\ufeff) cannot evade redaction."""
    evasion_email = "alice\u200b@example.com"
    payload = {"text": f"Contact me at {evasion_email}", "mode": "replace"}
    response = client.post("/redact", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["has_secrets"] is True
    assert "alice" not in data["clean_text"]
    assert "<EMAIL_ADDRESS>" in data["clean_text"]


def test_payload_too_large(client):
    """Test that oversized payloads (>500,000 chars) are safely rejected with HTTP 413."""
    large_text = "A" * 500001
    payload = {"text": large_text, "mode": "replace"}
    response = client.post("/redact", json=payload)
    assert response.status_code == 413
    assert "Payload too large" in response.json()["detail"]



