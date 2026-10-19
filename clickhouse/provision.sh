#!/usr/bin/env bash
# ==============================================================================
# CHouse UI - Default ClickHouse Connection & RBAC Policy Seeding
# Called by ../start.sh after the CHouse UI and PostgreSQL readiness gates.
# Idempotent: safe to re-run, updates the existing connection/policy rows in
# place.
#
# Works with the PostgreSQL RBAC backend (RBAC_DB_TYPE=postgres).
# Reads CLICKHOUSE_PASSWORD from the environment or .env if not already set.
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD:-$(grep '^CLICKHOUSE_PASSWORD=' .env 2>/dev/null | cut -d'=' -f2-)}"

if [[ -z "$CLICKHOUSE_PASSWORD" ]]; then
    echo "ERROR: CLICKHOUSE_PASSWORD is not set and could not be read from .env" >&2
    exit 1
fi

echo "Seeding the default ClickHouse connection in CHouse UI (PostgreSQL backend)..."

# Encrypt the password using the same encryptPassword helper that Chouse UI uses,
# running inside the chouse-ui container so it uses the live RBAC encryption key.
ENC_PASS=$(docker compose exec -T -e CLICKHOUSE_PASSWORD="${CLICKHOUSE_PASSWORD}" chouse-ui bun -e "
import { encryptPassword } from './packages/server/src/rbac/services/connections.ts';
process.stdout.write(encryptPassword(process.env.CLICKHOUSE_PASSWORD));
")

# Now upsert all RBAC rows directly into PostgreSQL
docker compose exec -T postgres psql -U postgres -d chouse_ui -v enc_pass="${ENC_PASS}" <<'EOF'
-- 1. Default ClickHouse connection
INSERT INTO rbac_clickhouse_connections
    (id, name, host, port, username, password_encrypted, database,
     is_default, is_active, ssl_enabled, created_at, updated_at)
VALUES
    ('00000000-0000-0000-0000-000000000001',
     'ClickHouse Stack', 'clickhouse', 8123, 'clickhouse',
     :'enc_pass',
     'default', true, true, false,
     now(), now())
ON CONFLICT (id) DO UPDATE SET
    username          = EXCLUDED.username,
    password_encrypted = EXCLUDED.password_encrypted,
    updated_at        = EXCLUDED.updated_at;

-- 2. Full-access data policy
INSERT INTO rbac_data_access_policies
    (id, name, description, is_system, created_at, updated_at)
VALUES
    ('11111111-1111-1111-1111-111111111111',
     'Full ClickHouse Access Policy',
     'Grants access to default ClickHouse connection',
     true,
     now(), now())
ON CONFLICT (id) DO NOTHING;

-- 3. Policy rule: allow all databases + tables on the default connection
INSERT INTO rbac_data_access_policy_rules
    (id, policy_id, connection_id, database_pattern, table_pattern,
     is_allowed, priority, created_at, updated_at)
VALUES
    ('22222222-2222-2222-2222-222222222222',
     '11111111-1111-1111-1111-111111111111',
     '00000000-0000-0000-0000-000000000001',
     '*', '*', true, 100,
     now(), now())
ON CONFLICT (id) DO NOTHING;

-- 4. Attach the policy to every existing role
INSERT INTO rbac_role_data_access_policies (id, role_id, policy_id, created_at)
SELECT
    'link_' || substring(id::text, 1, 8),
    id,
    '11111111-1111-1111-1111-111111111111',
    now()
FROM rbac_roles
ON CONFLICT (id) DO NOTHING;

-- 5. Ensure admin users have the super_admin role explicitly assigned
INSERT INTO rbac_user_roles (id, user_id, role_id, assigned_at)
SELECT
    gen_random_uuid(),
    u.id,
    r.id,
    now()
FROM rbac_users u, rbac_roles r
WHERE u.email LIKE 'admin@%' AND r.name = 'super_admin'
ON CONFLICT (user_id) DO UPDATE SET role_id = EXCLUDED.role_id;

EOF

echo "   -> ClickHouse connection + RBAC policy seeded OK"

