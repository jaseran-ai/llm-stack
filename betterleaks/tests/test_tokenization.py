"""Unit tests for Betterleaks reversible vaulted tokenization."""
import pytest
from fastapi.testclient import TestClient
from app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_tokenize_and_detokenize_roundtrip(client):
    secret_pat = "ghp_123456789012345678901234567890123456"  # gitleaks:allow
    prompt = f"Write a script that uses token: {secret_pat}"

    # 1. Tokenize
    tok_resp = client.post(
        "/tokenize",
        json={"text": prompt, "ttl_seconds": 60}
    )
    assert tok_resp.status_code == 200
    tok_data = tok_resp.json()
    assert tok_data["has_secrets"] is True
    assert tok_data["findings_count"] >= 1
    assert secret_pat not in tok_data["tokenized_text"]
    assert "TOK_GITHUB_PAT_" in tok_data["tokenized_text"]

    tokenized_text = tok_data["tokenized_text"]
    github_tok = next(t["token"] for t in tok_data["tokens"] if t["entity_type"] == "GITHUB_PAT")

    # 2. Simulate LLM reasoning on the surrogate token
    llm_simulated_output = f"Here is the script:\ncurl -H 'Authorization: Bearer {github_tok}' https://api.github.com/user"

    # 3. Detokenize / Rehydrate
    detok_resp = client.post(
        "/detokenize",
        json={"text": llm_simulated_output}
    )
    assert detok_resp.status_code == 200
    detok_data = detok_resp.json()
    assert detok_data["rehydrated_count"] == 1
    assert secret_pat in detok_data["detokenized_text"]
    assert github_tok not in detok_data["detokenized_text"]


def test_tokenize_clean_text(client):
    clean_prompt = "Hello, what is two plus two?"
    resp = client.post(
        "/tokenize",
        json={"text": clean_prompt}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_secrets"] is False
    assert data["tokenized_text"] == clean_prompt
    assert len(data["tokens"]) == 0


def test_detokenize_no_tokens(client):
    text = "Nothing to rehydrate here."
    resp = client.post(
        "/detokenize",
        json={"text": text}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rehydrated_count"] == 0
    assert data["detokenized_text"] == text


def test_redis_storage_is_encrypted(client):
    from app import get_redis_client
    r_client = get_redis_client()

    secret_key = "ghp_987654321098765432109876543210987654"  # gitleaks:allow
    prompt = f"Export token: {secret_key}"

    resp = client.post("/tokenize", json={"text": prompt, "ttl_seconds": 60})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["tokens"]) >= 1
    token = data["tokens"][0]["token"]

    # Directly inspect Redis raw stored value
    raw_redis_val = r_client.get(f"betterleaks:token:{token}")
    assert raw_redis_val is not None
    # Ensure raw secret is NOT in Redis in plaintext
    assert secret_key not in raw_redis_val
    # Ensure it is encrypted with 'enc:' prefix
    assert raw_redis_val.startswith("enc:")

    # Detokenize must seamlessly decrypt it back
    detok_resp = client.post("/detokenize", json={"text": token})
    assert detok_resp.json()["detokenized_text"] == secret_key
