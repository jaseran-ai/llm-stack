#!/usr/bin/env python3
"""Open WebUI post-startup provisioning: web search fix, RBAC fix, knowledge base, model access.

Extracted from open-webui/provision.sh (originally one large inline `python3 -c "..."`
heredoc) so it can be linted/read/tested like normal Python instead of living inside a bash
string. Behavior is unchanged.

Authentication note: Open WebUI is configured with WEBUI_AUTH_TRUSTED_EMAIL_HEADER (see
docker-compose.yml), the same "X-Authentik-Email" header the Authentik forward-auth outpost
passes through Traefik for real users (see
../authentik/README.md). Calling /api/v1/auths/signin directly against the container's mapped
port with that header set logs us in as the admin without ever needing to know a password -
simpler than the OIDC dance used by the Langfuse/LiteLLM provisioning scripts, because Open
WebUI has this native trusted-header shortcut and they don't.

Requires OPEN_WEBUI_PORT to be set in the environment (exported by start.sh from .env, defaults
to 8080), and PDF_PATH to point at the example knowledge-base PDF.
"""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from http_client import Session

KB_NAME = "AAPL 10-Q Example Knowledge"
MODEL_ID = "knowledge-search-assistant"
BASE_MODEL_ID = "lfm2.5-thinking-1.2b"
# Every LiteLLM-backed base model, aliased in litellm/litellm-config.yaml (see ollama/README.md).
BASE_MODEL_IDS = ["lfm2.5-thinking-1.2b", "lfm2.5-thinking-1.2b-no-think", "lfm2.5-thinking-1.2b-protected"]

# Public read access ('user'/'*' wildcard grant) is required on EVERY model below, including
# the 3 plain base models from the LiteLLM connection: this Open WebUI version's access model
# (open_webui/utils/models.py get_filtered_models()) defaults to deny for the 'user' role -
# only admins can see a connection-discovered model that has no DB row / no explicit grant
# at all, and an empty 'access_grants': [] list (rather than a public wildcard grant) means
# private/owner-only, not unrestricted. Confirmed empirically: alice (role 'user') saw
# 0 of 5 models via GET /api/models before this fix (admin saw all 5), because none of them
# had a public grant. A grant of {'principal_type': 'user', 'principal_id': '*', 'permission':
# 'read'} is Open WebUI's documented equivalent of the legacy 'access_control: null' (public)
# value - see open_webui/models/access_grants.py's access_control_to_grants().
PUBLIC_READ_GRANT = [{"principal_type": "user", "principal_id": "*", "permission": "read"}]


def upsert_model(session: Session, base: str, headers: dict, model_id: str, body: dict) -> bool:
    r_get = session.get(f"{base}/api/v1/models/model", headers=headers, params={"id": model_id}, timeout=15)
    if r_get.status_code == 200 and r_get.json():
        r_model = session.post(
            f"{base}/api/v1/models/model/update", headers=headers, params={"id": model_id}, json=body, timeout=15
        )
        action = "updated"
    else:
        r_model = session.post(f"{base}/api/v1/models/create", headers=headers, json=body, timeout=15)
        action = "created"
    ok = r_model.status_code == 200
    print(f'   -> Model "{model_id}" {action}:', "OK" if ok else f"FAILED (HTTP {r_model.status_code}: {r_model.text[:200]})")
    return ok


def fix_web_search(session: Session, base: str, headers: dict) -> None:
    # 1. Fix web search: the ENABLE_RAG_WEB_SEARCH / RAG_WEB_SEARCH_ENGINE env var names used
    # historically are not read by this Open WebUI version (renamed upstream to
    # ENABLE_WEB_SEARCH / WEB_SEARCH_ENGINE). Because Open WebUI seeds its config table once on
    # first boot and never re-reads env vars afterward, docker-compose.yml alone can't fix an
    # already-seeded 'disabled' value - it must be corrected here too.
    try:
        r = session.post(
            f"{base}/api/v1/retrieval/config/update",
            headers=headers,
            json={
                "ENABLE_RETRIEVAL_QUERY_GENERATION": False,
                "web": {
                    "ENABLE_WEB_SEARCH": True,
                    "WEB_SEARCH_ENGINE": "searxng",
                    "SEARXNG_QUERY_URL": "http://searxng:8080/search?q=<query>",
                },
            },
            timeout=15,
        )
        print("   -> SearXNG web search config:", "OK" if r.status_code == 200 else f"FAILED (HTTP {r.status_code})")
    except Exception as e:
        print(f"   -> SearXNG web search config failed ({e})")


def fix_rbac(session: Session, base: str, headers: dict, admin_email: str) -> None:
    # 2. Fix RBAC: every Authentik-authenticated user (even the 'users' group, e.g. alice/bob)
    # was being auto-provisioned as an Open WebUI 'admin' because of DEFAULT_USER_ROLE=admin,
    # regardless of their actual Authentik group. docker-compose.yml sets DEFAULT_USER_ROLE=user,
    # but that env var only seeds the DB config key on very first container boot - once written,
    # it is never re-read (same seed-once pattern as DEFAULT_MODELS, see ollama/README.md). A
    # deployment that was ever started before this env var existed (or before this fix) keeps
    # 'admin' persisted in the DB forever, so the env var alone cannot be trusted - confirmed
    # empirically: GET /api/v1/auths/admin/config still returned DEFAULT_USER_ROLE=admin on this
    # stack, and a brand new account (bob's first-ever sign-in) was auto-provisioned as 'admin'
    # because of it, even though alice (created earlier) was already 'user'.

    # 2a. Force the persisted admin-config value directly via the API (the only way to correct an
    # already-seeded config key), so every *future* first-time sign-in gets the right role too -
    # not just a one-off fix for accounts that already exist.
    try:
        r_cfg = session.get(f"{base}/api/v1/auths/admin/config", headers=headers, timeout=15)
        r_cfg.raise_for_status()
        admin_config = r_cfg.json()
        if admin_config.get("DEFAULT_USER_ROLE") != "user":
            admin_config["DEFAULT_USER_ROLE"] = "user"
            r_cfg_update = session.post(
                f"{base}/api/v1/auths/admin/config", headers=headers, json=admin_config, timeout=15
            )
            r_cfg_update.raise_for_status()
            print("   -> DEFAULT_USER_ROLE admin-config corrected: admin -> user")
        else:
            print("   -> DEFAULT_USER_ROLE admin-config already correct (user)")
    except Exception as e:
        print(f"   -> DEFAULT_USER_ROLE admin-config fix failed ({e})")

    # 2b. Retroactively demote any account that already exists with 'admin' (other than the real
    # admin) - covers accounts created before the 2a fix above (or before this script existed).
    try:
        r = session.get(f"{base}/api/v1/users/all", headers=headers, timeout=15)
        r.raise_for_status()
        users = r.json().get("users", [])
        demoted = []
        for u in users:
            if u.get("email") != admin_email and u.get("role") == "admin":
                uid = u["id"]
                ur = session.post(
                    f"{base}/api/v1/users/{uid}/update", headers=headers, json={"role": "user"}, timeout=15
                )
                if ur.status_code == 200:
                    demoted.append(u.get("email"))
        print(f"   -> Non-admin accounts demoted to the 'user' role: {demoted if demoted else 'none'}")
    except Exception as e:
        print(f"   -> RBAC role audit failed ({e})")


def provision_knowledge_base(session: Session, base: str, headers: dict, pdf_path: str) -> str | None:
    # 3. Example Knowledge Base (Qdrant-backed RAG) seeded from a real SEC 10-Q filing PDF.
    # Idempotent: creates the knowledge base only if missing, and (re-)attaches the PDF only if
    # it doesn't already have at least one file (self-healing if a previous run was interrupted
    # between the two steps).
    kb_id = None
    needs_file = True
    try:
        r = session.get(f"{base}/api/v1/knowledge/", headers=headers, timeout=15)
        r.raise_for_status()
        existing = [k for k in r.json().get("items", []) if k.get("name") == KB_NAME]
        if existing:
            kb_id = existing[0]["id"]
            needs_file = existing[0].get("file_count", 0) == 0
            print(f'   -> Knowledge base "{KB_NAME}" already exists (id={kb_id}, file_count={existing[0].get("file_count", 0)}).')
        else:
            r_kb = session.post(
                f"{base}/api/v1/knowledge/create",
                headers=headers,
                json={
                    "name": KB_NAME,
                    "description": "Apple Inc. 10-Q SEC filing (quarter ended June 27, 2026), provisioned as a working RAG example.",
                },
                timeout=15,
            )
            r_kb.raise_for_status()
            kb_id = r_kb.json()["id"]
            print(f'   -> Knowledge base "{KB_NAME}" created (id={kb_id}).')

        if kb_id and needs_file:
            with open(pdf_path, "rb") as fh:
                r_file = session.post(
                    f"{base}/api/v1/files/",
                    headers=headers,
                    files={"file": ("aapl-20260627.pdf", fh, "application/pdf")},
                    timeout=60,
                )
            r_file.raise_for_status()
            file_id = r_file.json()["id"]

            # File content extraction runs asynchronously right after upload (status starts as
            # 'pending', then 'processing', then 'completed'/'failed') - attaching the file to the
            # knowledge base before extraction finishes fails with a 400 ('content is empty').
            for _ in range(60):
                r_status = session.get(f"{base}/api/v1/files/{file_id}/process/status", headers=headers, timeout=15)
                file_status = r_status.json().get("status") if r_status.status_code == 200 else None
                if file_status in ("completed", "failed", None):
                    break
                time.sleep(2)

            r_attach = session.post(
                f"{base}/api/v1/knowledge/{kb_id}/file/add", headers=headers, json={"file_id": file_id}, timeout=120
            )
            r_attach.raise_for_status()
            print(f'   -> PDF embedded into knowledge base "{KB_NAME}" (id={kb_id}).')
    except Exception as e:
        print(f"   -> Knowledge base provisioning failed ({e}), step skipped (re-run manually if needed).")
    return kb_id


def provision_models(session: Session, base: str, headers: dict, kb_id: str | None) -> None:
    # 4. Custom model preset wiring the base LiteLLM model to the knowledge base above, with the
    # web search capability toggle exposed in the chat composer.

    # 4a. Base models: create a pass-through DB override (base_model_id=None, same id as the
    # upstream connection model) for each of the 3 LiteLLM-backed models, purely to attach a
    # public read access_grants entry - without a DB row at all, non-admin users can never see
    # them regardless of any other setting.
    try:
        for base_model_id in BASE_MODEL_IDS:
            upsert_model(
                session,
                base,
                headers,
                base_model_id,
                {
                    "id": base_model_id,
                    "base_model_id": None,
                    "name": base_model_id,
                    "params": {},
                    "meta": {},
                    "is_active": True,
                    "access_grants": PUBLIC_READ_GRANT,
                },
            )
    except Exception as e:
        print(f"   -> Base model access-grant provisioning failed ({e}), step skipped (re-run manually if needed).")

    try:
        model_body = {
            "id": MODEL_ID,
            "base_model_id": BASE_MODEL_ID,
            "name": "Knowledge & Search Assistant",
            "params": {
                "system": "You are a helpful assistant with access to a knowledge base and web search. Use the attached knowledge and, when enabled, live web search results to answer accurately.",
                # lfm2.5-thinking-1.2b (CPU-only, no GPU - see ollama/README.md) is a hybrid
                # thinking model that can otherwise reason indefinitely with no natural stopping
                # point for open-ended prompts - confirmed empirically (a single test completion
                # ran past 1000 tokens / 20+ minutes on constrained CPU with no max_tokens set).
                # Capping it here applies to every call using this model, including Open WebUI's
                # own internal follow-up completions, not just the user-facing one.
                "max_tokens": 300,
            },
            "meta": {
                "description": "Example model wired to the AAPL 10-Q knowledge base (Qdrant RAG) with SearXNG web search available.",
                "capabilities": {"web_search": True},
                **({"knowledge": [{"type": "collection", "id": kb_id, "name": KB_NAME}]} if kb_id else {}),
            },
            "is_active": True,
            "access_grants": PUBLIC_READ_GRANT,
        }
        upsert_model(session, base, headers, MODEL_ID, model_body)
    except Exception as e:
        print(f"   -> Model provisioning failed ({e}), step skipped (re-run manually if needed).")


def main() -> None:
    port = os.environ.get("OPEN_WEBUI_PORT", "8080")
    pdf_path = os.environ["PDF_PATH"]
    base = f"http://localhost:{port}"
    admin_email = "admin@example.com"

    session = Session(timeout=15)

    try:
        r = session.post(
            f"{base}/api/v1/auths/signin",
            headers={"X-Authentik-Email": admin_email, "X-Authentik-Name": "Admin"},
            json={"email": admin_email, "password": "unused"},
            timeout=15,
        )
        r.raise_for_status()
        token = r.json()["token"]
    except Exception as e:
        print(f"   -> Open WebUI admin signin failed ({e}), step skipped (re-run manually if needed).")
        return

    headers = {"Authorization": f"Bearer {token}"}

    fix_web_search(session, base, headers)
    fix_rbac(session, base, headers, admin_email)
    kb_id = provision_knowledge_base(session, base, headers, pdf_path)
    provision_models(session, base, headers, kb_id)


if __name__ == "__main__":
    main()
