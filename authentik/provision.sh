#!/usr/bin/env bash
# ==============================================================================
# Authentik - Blueprint, Outpost & Account Reconciliation Gate
# Runs as the one-shot authentik-provision Compose service after the Authentik
# server and worker have both passed their health checks.
#
# Authentik is this stack's SSO/IdP - see ../authentik/README.md for the full
# rationale (real admin UI, reliable "groups" OIDC claim, native forward-auth
# outposts).
#
# Native Declarative Blueprints: authentik/blueprints/*.yaml files use native
# Authentik !Env and !Format tags evaluated directly at runtime inside the
# container. They are mounted read-only into the containers at /blueprints/custom/
# (NOT mounted directly at /blueprints, which would shadow Authentik's own built-in
# system/default blueprints).
#
# Blueprint apply is asynchronous and NOT synchronous with container startup
# (confirmed empirically: a freshly-discovered blueprint sits in "unknown" status
# for several seconds before settling to "successful") - this script polls each
# custom blueprint's status via the API until it settles, rather than assuming
# it's already applied once the container reports healthy.
#
# The actual Python logic for each step below lives in authentik/scripts/*.py - this
# script is a thin bash orchestrator calling each step in order.
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

: "${AUTHENTIK_BASE_URL:?AUTHENTIK_BASE_URL must be set explicitly}"
: "${AUTHENTIK_BOOTSTRAP_TOKEN:?AUTHENTIK_BOOTSTRAP_TOKEN must be set explicitly}"
: "${DOMAIN:?DOMAIN must be set explicitly}"
: "${UI_PASSWORD:?UI_PASSWORD must be set explicitly}"
: "${AUTHENTIK_ACCOUNT_SECRETS_FILE:=/run/secrets/authentik.env}"
if [[ ! -r "${AUTHENTIK_ACCOUNT_SECRETS_FILE}" ]]; then
    echo "ERROR: Authentik account secrets were not rendered by Vault Agent." >&2
    exit 1
fi
set -a
# shellcheck disable=SC1090
source "${AUTHENTIK_ACCOUNT_SECRETS_FILE}"
set +a
: "${ALICE_PASSWORD:?ALICE_PASSWORD must be set explicitly}"
: "${BOB_PASSWORD:?BOB_PASSWORD must be set explicitly}"

echo "Reconciling Authentik blueprints, outpost bindings, and user passwords..."

# 1. Poll each custom blueprint's apply status until it settles (see the script's own
# docstring for the concurrent-apply deadlock this works around).
python3 "$REPO_DIR/authentik/scripts/wait_for_blueprints.py"

# 2. Wait until the embedded outpost serves the configured forward-auth endpoint
# (outpost provider bindings and brand domain are declared via 99-embedded-outpost.yaml).
python3 "$REPO_DIR/authentik/scripts/wait_for_outpost.py"

# 3. Synchronize standard account passwords (admin, alice, bob) via API.
python3 "$REPO_DIR/authentik/scripts/sync_user_passwords.py"
