#!/usr/bin/env bash
# ==============================================================================
# Grafana - Deterministic Datasource UID Migration
# Called by ../start.sh before Grafana starts (only touches the grafana_data
# volume directly while the container is not running yet - a running Grafana
# can hold an exclusive lock on its SQLite database).
#
# Why this exists: alert rules provisioned as code (grafana/provisioning/alerting)
# must reference a datasource by a stable, predictable UID. Grafana's own
# provisioning only auto-generates a random UID for a datasource the first time
# it's created - fine for a brand new deployment (this script has nothing to do
# in that case), but any datasource created by an OLDER version of this repo
# (before explicit "uid:" fields were added to datasources.yml) already has a
# random UID baked into its own database. Grafana's provisioning reconciler does
# NOT support changing an existing datasource's UID in place (confirmed
# empirically: it crashes the whole container with "Datasource provisioning
# error: data source not found" instead of migrating it) - so this script
# patches the stored UID directly, exactly the same "direct DB patch" pattern
# already used elsewhere in this project (LiteLLM's proxy_admin promotion,
# ClickHouse UI's RBAC seeding).
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

if docker volume inspect llm-stack_grafana_data >/dev/null 2>&1; then
  echo "Checking Grafana datasource UIDs for a pre-existing deployment..."
  docker run --rm -v llm-stack_grafana_data:/data python:3.11-alpine python3 -c "
import sqlite3, os

db_path = '/data/grafana.db'
if not os.path.exists(db_path):
    print('   -> No grafana.db yet (fresh deployment), nothing to migrate.')
else:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    expected = {'Prometheus': 'Prometheus', 'Loki': 'loki'}
    changed = []
    for name, wanted_uid in expected.items():
        cur.execute('SELECT uid FROM data_source WHERE name = ?', (name,))
        row = cur.fetchone()
        if row and row[0] != wanted_uid:
            cur.execute('UPDATE data_source SET uid = ? WHERE name = ?', (wanted_uid, name))
            changed.append(f'{name}: {row[0]} -> {wanted_uid}')
    if changed:
        conn.commit()
        print('   -> Migrated datasource UIDs: ' + ', '.join(changed))
    else:
        print('   -> Datasource UIDs already correct, nothing to do.')
    conn.close()
"
fi
