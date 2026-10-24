#!/usr/bin/env bash
# ==============================================================================
# Apply the repository's GitHub security settings and the main-branch ruleset
# (.github/rulesets/main.json) with the GitHub CLI. Idempotent.
#
# Usage: scripts/github_harden.sh [--dry-run] [OWNER/REPO]
#   OWNER/REPO defaults to the repository of the current checkout (gh repo view).
#   Requires `gh auth login` with admin rights on the repository.
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RULESET_FILE="$REPO_DIR/.github/rulesets/main.json"
DRY_RUN=false
REPO=""
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        *) REPO="$arg" ;;
    esac
done
[ -n "$REPO" ] || REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"

# api METHOD PATH [JSON_BODY]
api() {
    local method="$1" path="$2" body="${3:-}"
    if [ "$DRY_RUN" = true ]; then
        echo "DRY-RUN: gh api -X ${method} repos/${REPO}${path} ${body}"
        return 0
    fi
    if [ -n "$body" ]; then
        gh api -X "$method" "repos/${REPO}${path}" --input - <<<"$body" >/dev/null
    else
        gh api -X "$method" "repos/${REPO}${path}" >/dev/null
    fi
}

echo "Hardening ${REPO}..."

# GitHub Actions: only GitHub-owned actions and the reviewed third-party one, always
# pinned to a full commit SHA; read-only default token; workflows cannot approve PRs;
# every external contributor's workflow run needs a maintainer's approval.
api PUT /actions/permissions '{"enabled": true, "allowed_actions": "selected", "sha_pinning_required": true}'
api PUT /actions/permissions/selected-actions '{"github_owned_allowed": true, "verified_allowed": false, "patterns_allowed": ["aquasecurity/trivy-action@*"]}'
api PUT /actions/permissions/workflow '{"default_workflow_permissions": "read", "can_approve_pull_request_reviews": false}'
api PUT /actions/permissions/fork-pr-contributor-approval '{"approval_policy": "all_external_contributors"}'

# Secret scanning with push protection, private vulnerability reporting (SECURITY.md),
# Dependabot alerts and security updates.
api PATCH "" '{"security_and_analysis": {"secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}}}'
api PUT /private-vulnerability-reporting
api PUT /vulnerability-alerts
api PUT /automated-security-fixes

# Main-branch ruleset: create it, or update the existing ruleset with the same name.
ruleset_name="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["name"])' "$RULESET_FILE")"
ruleset_id=""
if [ "$DRY_RUN" = false ]; then
    ruleset_id="$(gh api "repos/${REPO}/rulesets" --jq ".[] | select(.name == \"${ruleset_name}\") | .id")"
fi
if [ -n "$ruleset_id" ]; then
    api PUT "/rulesets/${ruleset_id}" "$(cat "$RULESET_FILE")"
    echo "   -> Ruleset \"${ruleset_name}\" updated (id ${ruleset_id})."
else
    api POST /rulesets "$(cat "$RULESET_FILE")"
    echo "   -> Ruleset \"${ruleset_name}\" created."
fi
echo "Done."
