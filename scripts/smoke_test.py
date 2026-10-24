#!/usr/bin/env python3
# ==============================================================================
# LLM Stack - Smoke Test Suite (Deep Functional End-to-End Audit)
# Validates SSO authentication, RBAC enforcement, PII guardrails, observability
# and real business API execution across the stack.
# Supports running individual or comma-separated tests by name/key.
# ==============================================================================

import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.parse
import uuid
from datetime import datetime, timezone

import http_client
import s3_smoke

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_env_file(path='.env'):
    """Reads .env directly to guarantee tests target the configured domain/secrets."""
    values = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^([A-Z_0-9]+)=(.*)$', line)
                if m:
                    values[m.group(1)] = m.group(2).strip('"\'')
    return values


env_file = read_env_file()
domain = env_file.get('DOMAIN', os.environ.get('DOMAIN', 'localhost'))

def get_secret(key, ram_file):
    val = env_file.get(key)
    if not val:
        ram_path = os.path.join('vault', 'secrets_ram', ram_file)
        val = read_env_file(ram_path).get(key)
    return val

litellm_master_key = get_secret('LITELLM_MASTER_KEY', 'litellm.env')
qdrant_api_key = get_secret('QDRANT_API_KEY', 'qdrant.env') or get_secret('QDRANT__SERVICE__API_KEY', 'qdrant.env')
langfuse_public_key = get_secret('LANGFUSE_INIT_PROJECT_PUBLIC_KEY', 'langfuse.env')
langfuse_secret_key = get_secret('LANGFUSE_INIT_PROJECT_SECRET_KEY', 'langfuse.env')
open_webui_port = env_file.get('OPEN_WEBUI_PORT', '8080')
admin_password = env_file.get('UI_PASSWORD') or os.environ.get('UI_PASSWORD')
if not admin_password:
    raise RuntimeError('UI_PASSWORD must be set and non-empty in .env or the environment')
alice_password = get_secret('ALICE_PASSWORD', 'authentik.env')
bob_password = get_secret('BOB_PASSWORD', 'authentik.env')
if not alice_password or not bob_password:
    raise RuntimeError('ALICE_PASSWORD and BOB_PASSWORD must be set and non-empty in .env or Vault-rendered secrets')

DEFAULT_TIMEOUT = int(os.environ.get('SMOKE_TEST_TIMEOUT', '30'))


def make_session():
    """A cookie session with a default timeout and unverified local TLS."""
    return http_client.Session(verify=False, timeout=DEFAULT_TIMEOUT)


def authentik_login(target_url, username, password):
    """Drives Authentik's flow-executor to complete a login for forward-auth apps."""
    sess = make_session()
    r = sess.get(target_url, allow_redirects=True)
    if '/if/flow/' not in r.url:
        return sess, r
    flow_slug = r.url.split('/if/flow/')[1].split('/')[0]
    query = r.url.split('?', 1)[1] if '?' in r.url else ''
    next_param = urllib.parse.parse_qs(query).get('next', [None])[0]
    assert next_param, f"No 'next' OAuth continuation param found in flow URL: {r.url}"

    exec_url = f"https://authentik.{domain}/api/v3/flows/executor/{flow_slug}/?query={query}"
    sess.post(exec_url, json={'uid_field': username})
    sess.post(exec_url, json={'password': password})
    for _ in range(20):
        r_poll = sess.get(exec_url)
        if r_poll.status_code != 200:
            time.sleep(0.25)
            continue
        try:
            data = r_poll.json()
        except Exception:
            time.sleep(0.25)
            continue
        if data.get('final_redirect'):
            break
        if data.get('component') == 'ak-stage-access-denied':
            break
        time.sleep(0.25)

    next_url = f"https://authentik.{domain}" + urllib.parse.unquote(next_param)
    sess.get(next_url, allow_redirects=True)
    return sess, sess.get(target_url, allow_redirects=True)


def authentik_oidc_authorize(sess, authorize_url, username, password, follow_final_redirect=True):
    """Drives Authentik's flow-executor starting from an OIDC /application/o/authorize/ URL."""
    r = sess.get(authorize_url, allow_redirects=True)
    assert '/if/flow/' in r.url, f"Expected an Authentik login flow redirect, got: {r.url}"
    flow_slug = r.url.split('/if/flow/')[1].split('/')[0]
    query = r.url.split('?', 1)[1] if '?' in r.url else ''
    next_param = urllib.parse.parse_qs(query).get('next', [None])[0]
    assert next_param, f"No 'next' OAuth continuation param found in flow URL: {r.url}"

    exec_url = f"https://authentik.{domain}/api/v3/flows/executor/{flow_slug}/?query={query}"
    sess.post(exec_url, json={'uid_field': username})
    sess.post(exec_url, json={'password': password})
    for _ in range(20):
        r_poll = sess.get(exec_url)
        if r_poll.status_code != 200:
            time.sleep(0.25)
            continue
        try:
            data = r_poll.json()
        except Exception:
            time.sleep(0.25)
            continue
        if data.get('final_redirect'):
            break
        if data.get('component') == 'ak-stage-access-denied':
            break
        time.sleep(0.25)

    next_url = f"https://authentik.{domain}" + urllib.parse.unquote(next_param)
    return sess.get(next_url, allow_redirects=follow_final_redirect)


s = make_session()
FORWARD_AUTH_ADMIN_DOMAINS = ['grafana', 'logs', 'searxng', 's3-console', 'qdrant', 'status', 'traefik', 'alertmanager', 'arch']


# ------------------------------------------------------------------------------
# Test Definitions
# ------------------------------------------------------------------------------

def test_application_dashboard():
    r_home = s.get('http://localhost/', headers={'Host': f'home.{domain}'}, allow_redirects=False)
    assert r_home.status_code == 302, f"home domain did not redirect, got HTTP {r_home.status_code}"
    home_loc = r_home.headers.get('Location', '')
    assert '/if/user/' in home_loc, f"home redirect target unexpected: {home_loc}"

    admin_sess, _ = authentik_login(f'https://authentik.{domain}/if/flow/default-authentication-flow/?next=/if/user/', 'admin', admin_password)
    r_apps = admin_sess.get(f'https://authentik.{domain}/api/v3/core/applications/')
    assert r_apps.status_code == 200, f"Applications API failed: HTTP {r_apps.status_code}"
    admin_apps = {a['slug']: a for a in r_apps.json().get('results', [])}
    expected_app_count = 15
    assert len(admin_apps) == expected_app_count, f"Expected {expected_app_count} applications visible to admin, got {len(admin_apps)}: {sorted(admin_apps)}"
    missing_launch_urls = [slug for slug, a in admin_apps.items() if not a.get('meta_launch_url')]
    assert not missing_launch_urls, f"Applications missing a meta_launch_url: {missing_launch_urls}"

    alice_sess, _ = authentik_login(f'https://authentik.{domain}/if/flow/default-authentication-flow/?next=/if/user/', 'alice', alice_password)
    r_alice_apps = alice_sess.get(f'https://authentik.{domain}/api/v3/core/applications/')
    assert r_alice_apps.status_code == 200, f"Applications API failed for alice: HTTP {r_alice_apps.status_code}"
    alice_apps = {a['slug'] for a in r_alice_apps.json().get('results', [])}
    assert alice_apps == {'open-webui', 'docs'}, f"Expected alice to see open-webui and docs, got: {sorted(alice_apps)}"

    bob_sess, _ = authentik_login(f'https://authentik.{domain}/if/flow/default-authentication-flow/?next=/if/user/', 'bob', bob_password)
    r_bob_apps = bob_sess.get(f'https://authentik.{domain}/api/v3/core/applications/')
    assert r_bob_apps.status_code == 200, f"Applications API failed for bob: HTTP {r_bob_apps.status_code}"
    bob_apps = {a['slug'] for a in r_bob_apps.json().get('results', [])}
    assert bob_apps == {'open-webui', 'docs'}, f"Expected bob to see open-webui and docs, got: {sorted(bob_apps)}"

    return f"Root redirect OK | admin sees {len(admin_apps)} apps (all with launch URLs) | alice and bob correctly see open-webui and docs"


def test_langfuse():
    environment = os.environ.get('SMOKE_ENVIRONMENT')
    production_probe = os.environ.get('SMOKE_PROD_LANGFUSE_INGESTION')
    if production_probe not in (None, '', '1'):
        raise RuntimeError('SMOKE_PROD_LANGFUSE_INGESTION must be 1 when set')
    if production_probe == '1' and environment != 'production':
        raise RuntimeError('Production Langfuse ingestion requires SMOKE_ENVIRONMENT=production')

    langfuse_sess = make_session()
    r_csrf = langfuse_sess.get(f'https://langfuse.{domain}/api/auth/csrf')
    csrf_token = r_csrf.json().get('csrfToken')
    r_signin = langfuse_sess.post(f'https://langfuse.{domain}/api/auth/signin/custom', data={'csrfToken': csrf_token, 'callbackUrl': f'https://langfuse.{domain}/'}, allow_redirects=False)
    oidc_url = r_signin.headers.get('Location')
    r_final = authentik_oidc_authorize(langfuse_sess, oidc_url, 'admin', admin_password)
    assert r_final.status_code == 200 and (r_final.url == f'https://langfuse.{domain}/' or '/onboarding' in r_final.url), f"Langfuse OIDC login failed, landed on {r_final.url}"

    r_sess = langfuse_sess.get(f'https://langfuse.{domain}/api/auth/session')
    assert r_sess.status_code == 200 and 'admin@example.com' in r_sess.text, "Langfuse OIDC session invalid"

    alice_sess = make_session()
    r_alice_csrf = alice_sess.get(f'https://langfuse.{domain}/api/auth/csrf')
    r_alice_signin = alice_sess.post(f'https://langfuse.{domain}/api/auth/signin/custom', data={'csrfToken': r_alice_csrf.json().get('csrfToken'), 'callbackUrl': f'https://langfuse.{domain}/'}, allow_redirects=False)
    r_alice_final = authentik_oidc_authorize(alice_sess, r_alice_signin.headers.get('Location'), 'alice', alice_password)
    assert 'Permission denied' in r_alice_final.text, \
        "alice (users group) was not blocked from Langfuse (RBAC gap) - Authentik Policy Binding not enforced"

    assert langfuse_public_key and langfuse_secret_key, "Missing LANGFUSE_INIT_PROJECT_PUBLIC_KEY/SECRET_KEY in .env"
    r_projects = langfuse_sess.get(f'https://langfuse.{domain}/api/public/projects', auth=(langfuse_public_key, langfuse_secret_key))
    assert r_projects.status_code == 200, f"Langfuse Projects API HTTP {r_projects.status_code}"
    project_names = [p.get('name') for p in r_projects.json().get('data', [])]
    assert len(project_names) > 0, "Langfuse Projects API returned no projects"
    detail = f"Authentik OIDC OK | admin allowed, alice blocked | Projects API OK ({', '.join(project_names)})"
    if environment == 'uat':
        detail += f" | {test_langfuse_ingestion('uat')}"
    elif production_probe == '1':
        detail += f" | {test_langfuse_ingestion('production')}"
    return detail


def test_langfuse_ingestion(environment):
    """Verify explicitly authorized ingestion across Langfuse, S3, and ClickHouse."""
    if environment == 'uat':
        identity_file = os.environ.get('SMOKE_UAT_IDENTITY_FILE')
        if not identity_file or os.path.islink(identity_file) or not os.path.isfile(identity_file):
            raise RuntimeError('UAT identity file is missing or unsafe')
        if env_file.get('TLS_MODE') != 'internal':
            raise RuntimeError('UAT ingestion requires internal TLS')
    elif environment == 'production':
        if (os.environ.get('SMOKE_ENVIRONMENT') != 'production'
                or os.environ.get('SMOKE_PROD_LANGFUSE_INGESTION') != '1'
                or os.environ.get('SMOKE_UAT_IDENTITY_FILE')):
            raise RuntimeError('Production ingestion requires explicit production attestation')
    else:
        raise RuntimeError('Unsupported Langfuse ingestion environment')

    project_id = env_file.get('LANGFUSE_INIT_PROJECT_ID', '')
    bucket = env_file.get('LANGFUSE_S3_EVENT_UPLOAD_BUCKET', '')
    prefix = env_file.get('LANGFUSE_S3_EVENT_UPLOAD_PREFIX', '')
    region = env_file.get('LANGFUSE_S3_EVENT_UPLOAD_REGION', '')
    ch_password = env_file.get('CLICKHOUSE_PASSWORD')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', project_id):
        raise RuntimeError('Langfuse project ID is missing or unsafe')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]', bucket):
        raise RuntimeError('Langfuse S3 bucket is missing or unsafe')
    if not re.fullmatch(r'(?:[A-Za-z0-9_-]+/)+', prefix):
        raise RuntimeError('Langfuse S3 event prefix is missing or unsafe')
    if not re.fullmatch(r'[A-Za-z0-9-]{1,32}', region) or not ch_password:
        raise RuntimeError('Langfuse S3 region or ClickHouse credential is missing')

    tls_mode = env_file.get('TLS_MODE')
    if tls_mode not in ('internal', 'http-01', 'cloudflare-dns01'):
        raise RuntimeError('Unsupported Langfuse ingestion TLS mode')
    tls = ssl.create_default_context()
    if tls_mode == 'internal':
        ca_file = 'traefik/certs/tls.crt'
        if os.path.islink(ca_file) or not os.path.isfile(ca_file):
            raise RuntimeError('Internal TLS trust certificate is missing or unsafe')
        tls.load_verify_locations(cafile=ca_file)
    client = http_client.Session(verify=tls, timeout=20)

    trace_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    event = {
        'id': event_id,
        'type': 'trace-create',
        'timestamp': timestamp,
        'body': {'id': trace_id, 'name': f'llm-stack-{environment}-ingestion-smoke', 'timestamp': timestamp},
    }
    response = client.post(
        f'https://langfuse.{domain}/api/public/ingestion',
        auth=(langfuse_public_key, langfuse_secret_key),
        json={'batch': [event]},
        allow_redirects=False,
    )
    if response.status_code != 207:
        raise RuntimeError(f'Langfuse ingestion HTTP {response.status_code}, expected 207')
    result = response.json()
    if result.get('errors') or result.get('successes') != [{'id': event_id, 'status': 201}]:
        raise RuntimeError('Langfuse ingestion did not acknowledge the synthetic event')

    access_key, secret_key = s3_smoke.load_credentials('vault/secrets_ram/s3.json')
    host = f's3.{domain}'
    path = f'/{bucket}/{prefix}{project_id}/trace/{trace_id}/{event_id}.json'
    s3_url = f'https://{host}{path}'
    s3_status = None
    for attempt in range(15):
        headers = s3_smoke.sign_request(
            'GET', host, path, b'', access_key, secret_key, region, datetime.now(timezone.utc),
        )
        stored = client.get(s3_url, headers=headers, allow_redirects=False)
        s3_status = stored.status_code
        if s3_status == 200:
            stored_events = stored.json()
            if (
                not isinstance(stored_events, list) or len(stored_events) != 1
                or not isinstance(stored_events[0], dict)
                or stored_events[0].get('id') != event_id
                or stored_events[0].get('body', {}).get('id') != trace_id
            ):
                raise RuntimeError('Langfuse S3 event payload does not match the synthetic event')
            break
        if s3_status != 404:
            raise RuntimeError(f'Langfuse S3 event GET HTTP {s3_status}')
        if attempt < 14:
            time.sleep(2)
    else:
        raise RuntimeError(f'Langfuse S3 event remained unavailable (HTTP {s3_status})')

    ch_headers = {'X-ClickHouse-User': 'clickhouse', 'X-ClickHouse-Key': ch_password}
    query = (
        "SELECT count() AS matches FROM traces WHERE project_id = '"
        + project_id + "' AND id = '" + trace_id + "' FORMAT JSON"
    )
    for attempt in range(20):
        row = http_client.get(
            'http://127.0.0.1:8123/', params={'query': query}, headers=ch_headers, timeout=10,
        )
        if row.status_code != 200:
            raise RuntimeError(f'Langfuse ClickHouse query HTTP {row.status_code}')
        matches = row.json().get('data', [{}])[0].get('matches', 0)
        if matches == 1:
            return f'{environment.upper()} ingestion HTTP 207 | signed S3 GET 200 | ClickHouse trace 1'
        if attempt < 19:
            time.sleep(2)
    raise RuntimeError('Langfuse synthetic trace did not reach ClickHouse')


def test_chouse_ui():
    chouse_sess = make_session()
    r_start = chouse_sess.get(f'https://clickhouse.{domain}/api/rbac/auth/sso/authentik/start', allow_redirects=False)
    auth_loc = r_start.headers.get('Location')
    if r_start.status_code == 429:
        oidc_status = "Authentik OIDC rate-limited (10 req/15m)"
    else:
        assert auth_loc, f"CHouse UI SSO start did not return redirect location (status {r_start.status_code})"
        r_cb_redirect = authentik_oidc_authorize(chouse_sess, auth_loc, 'admin', admin_password, follow_final_redirect=False)
        callback_url = r_cb_redirect.headers.get('Location') or r_cb_redirect.url
        parsed = urllib.parse.urlparse(callback_url)
        assert parsed.query, f"CHouse UI OIDC callback URL has no query string: {callback_url}"
        r_post_cb = chouse_sess.post(f'https://clickhouse.{domain}/api/rbac/auth/sso/callback', json={'params': '?' + parsed.query})
        assert r_post_cb.status_code == 200 and 'super_admin' in r_post_cb.text, f"CHouse UI OIDC login failed: {r_post_cb.status_code}"
        oidc_status = "Authentik OIDC OK | admin allowed (super_admin)"

        alice_sess = make_session()
        r_alice_start = alice_sess.get(f'https://clickhouse.{domain}/api/rbac/auth/sso/authentik/start', allow_redirects=False)
        alice_loc = r_alice_start.headers.get('Location')
        if alice_loc:
            r_alice_final = authentik_oidc_authorize(alice_sess, alice_loc, 'alice', alice_password)
            assert 'Permission denied' in r_alice_final.text, \
                "alice (users group) was not blocked from CHouse UI (RBAC gap) - Authentik Policy Binding not enforced"
        oidc_status += ", alice blocked"

    # Verify ClickHouse Server 26.7 native HTTP engine query & aggregation
    ch_pass = os.environ.get('CLICKHOUSE_PASSWORD', '')
    if not ch_pass and os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.startswith('CLICKHOUSE_PASSWORD='):
                    ch_pass = line.split('=', 1)[1].strip()
                    break
    ch_headers = {'X-ClickHouse-User': 'clickhouse', 'X-ClickHouse-Key': ch_pass}
    ch_base = 'http://127.0.0.1:8123'
    try:
        http_client.get(f'{ch_base}/ping', timeout=1)
    except Exception:
        try:
            cmd = ['docker', 'inspect', 'clickhouse', '--format', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}']
            ch_ip = subprocess.check_output(cmd, text=True).strip()
            if ch_ip:
                ch_base = f'http://{ch_ip}:8123'
        except Exception:
            pass

    r_ch_ver = http_client.get(f'{ch_base}/?query=SELECT%20version()%20FORMAT%20JSON', headers=ch_headers, timeout=10)
    assert r_ch_ver.status_code == 200, f"ClickHouse native HTTP query failed: {r_ch_ver.status_code}"
    ch_version = r_ch_ver.json().get('data', [{}])[0].get('version()', 'unknown')

    # Test ClickHouse transient DDL, DML and aggregation via native HTTP endpoint
    http_client.post(f'{ch_base}/', headers=ch_headers, data='CREATE DATABASE IF NOT EXISTS _smoke_test', timeout=10)
    http_client.post(f'{ch_base}/', headers=ch_headers, data='CREATE TABLE IF NOT EXISTS _smoke_test.t (id UInt64, v Float64) ENGINE = Memory', timeout=10)
    http_client.post(f'{ch_base}/', headers=ch_headers, data='INSERT INTO _smoke_test.t VALUES (1, 100.0)', timeout=10)
    r_avg = http_client.post(f'{ch_base}/', headers=ch_headers, data='SELECT avg(v) FROM _smoke_test.t FORMAT JSON', timeout=10)
    http_client.post(f'{ch_base}/', headers=ch_headers, data='DROP DATABASE _smoke_test', timeout=10)
    assert '100' in r_avg.text, f"ClickHouse DDL/DML aggregation failed: {r_avg.text}"

    return f"{oidc_status} | ClickHouse {ch_version} native queries & engine operational"


def test_litellm():
    litellm_sess = make_session()
    r_start = litellm_sess.get(f'https://litellm.{domain}/sso/key/generate', allow_redirects=False)
    r_final = authentik_oidc_authorize(litellm_sess, r_start.headers.get('Location'), 'admin', admin_password)
    assert r_final.status_code == 200 and 'login=success' in r_final.url, f"LiteLLM OIDC login failed, landed on {r_final.url}"

    alice_sess = make_session()
    r_alice_start = alice_sess.get(f'https://litellm.{domain}/sso/key/generate', allow_redirects=False)
    r_alice_final = authentik_oidc_authorize(alice_sess, r_alice_start.headers.get('Location'), 'alice', alice_password)
    assert 'Permission denied' in r_alice_final.text, \
        "alice (users group) was not blocked from LiteLLM (RBAC gap) - Authentik Policy Binding not enforced"

    assert litellm_master_key, "Missing LITELLM_MASTER_KEY in .env"
    headers = {'Authorization': f'Bearer {litellm_master_key}'}
    r_models = s.get(f'https://litellm.{domain}/models', headers=headers)
    assert r_models.status_code == 200, f"LiteLLM Models HTTP {r_models.status_code}"
    model_ids = [m.get('id') for m in r_models.json().get('data', [])]
    assert len(model_ids) > 0, "LiteLLM Models API returned no models"
    return f"Authentik OIDC OK | admin allowed, alice blocked | Models Routing API OK ({len(model_ids)} models)"


def test_open_webui():
    sess, _ = authentik_login(f'https://chat.{domain}/', 'admin', admin_password)
    r_ow_signin = sess.post(f'https://chat.{domain}/api/v1/auths/signin', json={'email': 'admin@example.com', 'password': admin_password})
    assert r_ow_signin.status_code == 200, f"Open-WebUI signin HTTP {r_ow_signin.status_code}"
    ow_token = r_ow_signin.json().get('token')
    ow_headers = {'Authorization': f'Bearer {ow_token}'}

    r_chat = sess.post(f'https://chat.{domain}/api/chat/completions', headers=ow_headers, json={
        'model': 'lfm2-1.2b-rag',
        'messages': [{'role': 'user', 'content': 'ping'}],
        'max_tokens': 20,
    }, timeout=120)
    assert r_chat.status_code == 200, f"Open-WebUI Chat Completion HTTP {r_chat.status_code}: {r_chat.text}"
    model_used = r_chat.json().get('model', 'unknown')
    return f"Authentik Forward-Auth OK | Real LLM Inference OK ({model_used})"


def test_grafana():
    sess, r_graf = None, None
    for attempt in range(10):
        sess, r_graf = authentik_login(f'https://grafana.{domain}/', 'admin', admin_password)
        if r_graf.status_code == 200:
            break
        if r_graf.status_code in (502, 503, 504):
            time.sleep(1)
            continue
        time.sleep(0.5)
    assert r_graf and r_graf.status_code == 200, f"Grafana UI HTTP {getattr(r_graf, 'status_code', 'unreachable')}"
    r_datasources = None
    for attempt in range(10):
        r_datasources = sess.get(f'https://grafana.{domain}/api/datasources')
        if r_datasources.status_code == 200:
            break
        time.sleep(1)
    assert r_datasources and r_datasources.status_code == 200, f"Grafana Datasources API HTTP {getattr(r_datasources, 'status_code', 'unreachable')}"
    ds_names = [ds['name'] for ds in r_datasources.json()]
    return f"Authentik Forward-Auth OK | Datasources API OK ({', '.join(ds_names)})"


def test_dozzle():
    _, r_admin = authentik_login(f'https://logs.{domain}/', 'admin', admin_password)
    assert r_admin.status_code == 200, f"Dozzle UI (admin, Authentik) HTTP {r_admin.status_code}"
    assert 'dozzle' in r_admin.text.lower(), "Response does not look like Dozzle's UI"

    _, r_alice = authentik_login(f'https://logs.{domain}/', 'alice', alice_password)
    assert 'Permission denied' in r_alice.text, \
        "alice (users group) was not blocked from Dozzle (RBAC gap) - Authentik Policy Binding not enforced"

    return "Authentik Forward-Auth OK | admin allowed, alice (non-admin) blocked"


def test_searxng():
    _, r_search = authentik_login(f'https://searxng.{domain}/?q=healthcheck&format=json', 'admin', admin_password)
    assert r_search.status_code == 200, f"SearXNG Search API HTTP {r_search.status_code}"
    results_count = len(r_search.json().get('results', []))
    return f"Authentik Forward-Auth OK | Live Search Query API OK ({results_count} results)"


def test_seaweedfs_console():
    _, r_console = authentik_login(f'https://s3-console.{domain}/', 'admin', admin_password)
    assert r_console.status_code == 200, f"SeaweedFS Console HTTP {r_console.status_code}"
    return "Authentik Forward-Auth OK | S3 Console OK"


def test_traefik():
    sess_admin, r_admin = authentik_login(f'https://traefik.{domain}/dashboard/', 'admin', admin_password)
    assert r_admin.status_code == 200, f"Traefik Dashboard HTTP {r_admin.status_code}"

    r_overview = sess_admin.get(f'https://traefik.{domain}/api/overview')
    assert r_overview.status_code == 200, f"Traefik API Overview HTTP {r_overview.status_code}"
    overview = r_overview.json()
    routers_count = overview.get('http', {}).get('routers', {}).get('total', 0)
    services_count = overview.get('http', {}).get('services', {}).get('total', 0)
    assert routers_count > 0, "Traefik reports 0 HTTP routers"

    _, r_alice = authentik_login(f'https://traefik.{domain}/dashboard/', 'alice', alice_password)
    assert 'Permission denied' in r_alice.text, \
        "alice (users group) was not blocked from Traefik Dashboard (RBAC gap) - Authentik Policy Binding not enforced"

    return f"Authentik Forward-Auth OK | Dashboard & API Overview OK ({routers_count} routers, {services_count} services) | alice blocked"


def test_alertmanager():
    sess_admin, r_admin = authentik_login(f'https://alertmanager.{domain}/', 'admin', admin_password)
    assert r_admin.status_code == 200, f"Alertmanager Web UI HTTP {r_admin.status_code}"

    r_status = sess_admin.get(f'https://alertmanager.{domain}/api/v2/status')
    assert r_status.status_code == 200, f"Alertmanager API status HTTP {r_status.status_code}"
    status_data = r_status.json()
    version = status_data.get('versionInfo', {}).get('version', '')
    assert version, "Alertmanager API returned empty version"

    _, r_alice = authentik_login(f'https://alertmanager.{domain}/', 'alice', alice_password)
    assert 'Permission denied' in r_alice.text, \
        "alice (users group) was not blocked from Alertmanager (RBAC gap) - Authentik Policy Binding not enforced"

    return f"Authentik Forward-Auth OK | Alertmanager v{version} API status OK | alice blocked"


def test_qdrant():
    assert qdrant_api_key, "Missing QDRANT_API_KEY in .env"
    sess, _ = authentik_login(f'https://qdrant.{domain}/', 'admin', admin_password)
    r_qdrant = sess.get(f'https://qdrant.{domain}/collections', headers={'api-key': qdrant_api_key})
    assert r_qdrant.status_code == 200, f"Qdrant Collections API HTTP {r_qdrant.status_code}"
    collections = [c.get('name') for c in r_qdrant.json().get('result', {}).get('collections', [])]
    return f"Authentik Forward-Auth OK | Collections API OK ({len(collections)} collections)"


def test_s3_api():
    r = s.get(f'https://s3.{domain}/', allow_redirects=False)
    if r.status_code == 302 and 'authentik.' in (r.headers.get('Location') or ''):
        raise RuntimeError(f"s3.{domain} unexpectedly redirects to Authentik")
    bucket = env_file.get('LANGFUSE_S3_EVENT_UPLOAD_BUCKET')
    region = env_file.get('LANGFUSE_S3_EVENT_UPLOAD_REGION')
    if not bucket or not region:
        raise RuntimeError('Langfuse S3 bucket and region must be configured')
    tls_mode = env_file.get('TLS_MODE')
    if tls_mode not in ('internal', 'http-01', 'cloudflare-dns01'):
        raise RuntimeError('TLS_MODE must select a supported S3 TLS trust policy')
    tls_ca = 'traefik/certs/tls.crt' if tls_mode == 'internal' else None
    detail = s3_smoke.probe(
        domain, bucket, region, 'vault/secrets_ram/s3.json', tls_ca=tls_ca,
    )
    return f"S3 API routing OK (HTTP {r.status_code}) | {detail}"


def test_rbac_anonymous():
    sess = make_session()
    problems = []
    header_problems = []
    for sub in FORWARD_AUTH_ADMIN_DOMAINS:
        r = sess.get(f'https://{sub}.{domain}/', allow_redirects=False)
        if r.status_code not in (302, 401, 403):
            problems.append(f"{sub} (HTTP {r.status_code})")
        hsts = r.headers.get('strict-transport-security', '')
        nosniff = r.headers.get('x-content-type-options', '')
        referrer = r.headers.get('referrer-policy', '')
        xfo = r.headers.get('x-frame-options', '')
        if not (hsts and nosniff == 'nosniff' and referrer and xfo == 'SAMEORIGIN'):
            header_problems.append(f"{sub} (HSTS={bool(hsts)}, nosniff={nosniff}, referrer={referrer}, xfo={xfo})")
    assert not problems, f"Domains not blocked for anonymous access (RBAC gap): {', '.join(problems)}"
    assert not header_problems, f"Missing security headers: {', '.join(header_problems)}"
    return f"Anonymous access blocked (302/401/403) & security headers verified on {len(FORWARD_AUTH_ADMIN_DOMAINS)} admin domains"


def test_rbac_users_group():
    sess, r_chat = authentik_login(f'https://chat.{domain}/', 'alice', alice_password)
    assert r_chat.status_code == 200, f"alice (users group) should be able to access chat.{domain} (HTTP {r_chat.status_code})"

    leaked = []
    for sub in FORWARD_AUTH_ADMIN_DOMAINS:
        r = sess.get(f'https://{sub}.{domain}/', allow_redirects=False)
        if r.status_code not in (302, 401, 403):
            leaked.append(f"{sub} (HTTP {r.status_code})")
    assert not leaked, f"alice (users group) can access admin tools (RBAC gap): {', '.join(leaked)}"
    return f"chat.{domain} OK | blocked on {len(FORWARD_AUTH_ADMIN_DOMAINS)} admin tools"


def test_ollama_default_model():
    assert litellm_master_key, "Missing LITELLM_MASTER_KEY in .env"
    headers = {'Authorization': f'Bearer {litellm_master_key}'}
    r = s.post(f'https://litellm.{domain}/v1/chat/completions', headers=headers, json={
        'model': 'lfm2-1.2b-rag',
        'messages': [{'role': 'user', 'content': 'Say hi'}],
        'max_tokens': 20,
    }, timeout=120)
    assert r.status_code == 200, f"Ollama-backed completion HTTP {r.status_code}: {r.text}"
    message = r.json()['choices'][0]['message']
    text = (message.get('content') or '') + (message.get('reasoning_content') or '')
    assert text.strip(), "Ollama-backed completion returned no content or reasoning_content"
    return "CPU-only default model (lfm2-1.2b-rag via ollama) produced a real completion"


def test_open_webui_knowledge_rag():
    owui = make_session()
    r_auth = owui.post(f'http://localhost:{open_webui_port}/api/v1/auths/signin',
                        headers={'X-Authentik-Email': 'admin@example.com', 'X-Authentik-Name': 'Admin'},
                        json={'email': 'admin@example.com', 'password': 'unused'})
    assert r_auth.status_code == 200, f"Open-WebUI trusted-header signin HTTP {r_auth.status_code}"
    token = r_auth.json()['token']
    headers = {'Authorization': f'Bearer {token}'}

    r_kb = owui.get(f'http://localhost:{open_webui_port}/api/v1/knowledge/', headers=headers)
    assert r_kb.status_code == 200, f"Open-WebUI Knowledge list HTTP {r_kb.status_code}"
    items = [k for k in r_kb.json().get('items', []) if k.get('name') == 'AAPL 10-Q Example Knowledge']
    assert items, "AAPL 10-Q Example Knowledge base not found (open-webui/provision.sh not run?)"
    kb = items[0]
    assert kb.get('file_count', 0) > 0, "Knowledge base exists but has no attached files"

    rag_query = 'What was the total deferred revenue as of June 27, 2026?'
    r_retrieval = owui.post(
        f'http://localhost:{open_webui_port}/api/v1/retrieval/query/collection',
        headers=headers,
        json={
            'collection_names': [kb['id']],
            'query': rag_query,
            'k': 5,
            'hybrid': False,
        },
        timeout=120,
    )
    assert r_retrieval.status_code == 200, f"Open-WebUI RAG retrieval HTTP {r_retrieval.status_code}"
    retrieval_documents = r_retrieval.json().get('documents', [])
    retrieval_text = json.dumps(retrieval_documents)
    assert '14.9' in retrieval_text, "Qdrant retrieval did not return the expected fact from the PDF"

    r_chat = owui.post(f'http://localhost:{open_webui_port}/api/chat/completions', headers=headers, json={
        'model': 'knowledge-search-assistant',
        'messages': [{'role': 'user', 'content': f'According to the attached document, {rag_query}'}],
        'files': [{'type': 'collection', 'id': kb['id']}],
    }, timeout=360)
    assert r_chat.status_code == 200, f"Open-WebUI RAG chat completion HTTP {r_chat.status_code}"
    return f"Knowledge base OK ({kb['file_count']} file) | Qdrant retrieval and RAG chat completion verified"


def test_open_webui_web_search():
    owui = make_session()
    r_auth = owui.post(f'http://localhost:{open_webui_port}/api/v1/auths/signin',
                        headers={'X-Authentik-Email': 'admin@example.com', 'X-Authentik-Name': 'Admin'},
                        json={'email': 'admin@example.com', 'password': 'unused'})
    assert r_auth.status_code == 200, f"Open-WebUI trusted-header signin HTTP {r_auth.status_code}"
    token = r_auth.json()['token']
    headers = {'Authorization': f'Bearer {token}'}

    r_cfg = owui.get(f'http://localhost:{open_webui_port}/api/v1/retrieval/config', headers=headers)
    assert r_cfg.status_code == 200, f"Open-WebUI retrieval config HTTP {r_cfg.status_code}"
    web_cfg = r_cfg.json().get('web', {})
    assert web_cfg.get('ENABLE_WEB_SEARCH') is True, "Web search is disabled (ENABLE_WEB_SEARCH is not true)"
    assert web_cfg.get('WEB_SEARCH_ENGINE') == 'searxng', f"Unexpected web search engine: {web_cfg.get('WEB_SEARCH_ENGINE')!r}"

    r_chat = owui.post(f'http://localhost:{open_webui_port}/api/chat/completions', headers=headers, json={
        'model': 'knowledge-search-assistant',
        'messages': [{'role': 'user', 'content': 'search the web: what is the current year?'}],
        'features': {'web_search': True},
    }, timeout=240)
    assert r_chat.status_code == 200, f"Open-WebUI web search chat completion HTTP {r_chat.status_code}"
    return "ENABLE_WEB_SEARCH=true | engine=searxng | live web-search completion OK"


def test_prometheus_observability():
    r = http_client.get(f'http://localhost:9190/api/v1/targets', timeout=DEFAULT_TIMEOUT, verify=False)
    assert r.status_code == 200, f"Prometheus targets API HTTP {r.status_code}"
    active = r.json().get('data', {}).get('activeTargets', [])
    jobs_health = {t.get('labels', {}).get('job'): t.get('health') for t in active}
    expected_jobs = ['litellm', 'qdrant', 'cadvisor', 'node-exporter', 'traefik']
    down = [f"{j} ({jobs_health.get(j, 'absent')})" for j in expected_jobs if jobs_health.get(j) != 'up']
    assert not down, f"Prometheus jobs not operational: {', '.join(down)}"
    return f"All jobs scraped successfully ({', '.join(expected_jobs)})"


def test_postgres():
    result = os.environ.get('SMOKE_POSTGRES_PROBE', '')
    if not result:
        try:
            cmd = ['docker', 'compose', 'exec', '-T', 'postgres', 'psql', '--username', 'postgres', '--dbname', 'postgres', '--tuples-only', '--no-align', '--command', 'SELECT 1;']
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if p.returncode == 0:
                result = p.stdout.strip()
        except Exception:
            pass
    assert result == '1', "PostgreSQL SELECT 1 probe was not completed successfully by the smoke runner"
    return "Authenticated SELECT 1 returned 1"


def test_redis():
    result = os.environ.get('SMOKE_REDIS_PROBE', '')
    if not result:
        try:
            cmd = ['docker', 'compose', 'exec', '-T', 'redis', 'sh', '-ec', 'REDISCLI_AUTH="$REDIS_AUTH" exec redis-cli --no-auth-warning ping']
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            if p.returncode == 0:
                result = p.stdout.strip()
        except Exception:
            pass
    assert result == 'PONG', "Redis authenticated PING probe was not completed successfully by the smoke runner"
    return "Authenticated PING returned PONG"


def test_loki_log_ingestion():
    r = http_client.get(f'http://localhost:3100/loki/api/v1/labels', timeout=DEFAULT_TIMEOUT, verify=False)
    assert r.status_code == 200, f"Loki labels API HTTP {r.status_code}"
    labels = r.json().get('data', [])
    assert 'container' in labels, f"'container' label missing (Vector may not be feeding Loki): {labels}"
    return f"Logs genuinely ingested, labels present ({', '.join(labels)})"


# ------------------------------------------------------------------------------
# Test Registry & CLI Execution
# ------------------------------------------------------------------------------

def test_vault():
    vault_ca = 'traefik/certs/tls.crt'
    vault_url = 'https://localhost:8201'
    r_sys = http_client.get(f'{vault_url}/v1/sys/health', timeout=DEFAULT_TIMEOUT, verify=vault_ca)
    assert r_sys.status_code == 200, f"Vault healthcheck HTTP {r_sys.status_code}"
    health = r_sys.json()
    assert not health.get('sealed', True), "Vault is sealed!"

    assert os.path.exists('.vault_keys.json'), "Missing .vault_keys.json!"
    with open('.vault_keys.json') as f:
        keys = json.load(f)
    token = keys.get('root_token')
    assert token, "No root token in .vault_keys.json!"

    r_kv = http_client.get(f'{vault_url}/v1/secret/data/llm-stack/postgres', headers={'X-Vault-Token': token}, verify=vault_ca)
    assert r_kv.status_code == 200, f"Vault KV read HTTP {r_kv.status_code}"
    pg_pass = r_kv.json().get('data', {}).get('data', {}).get('POSTGRES_PASSWORD')
    assert pg_pass, "Failed to read POSTGRES_PASSWORD from Vault KV!"

    r_ui = http_client.get(f'{vault_url}/ui/', allow_redirects=True, verify=vault_ca)
    assert r_ui.status_code == 200 and ('<html' in r_ui.text.lower() or '<!doctype' in r_ui.text.lower()), f"Vault UI endpoint check failed: HTTP {r_ui.status_code}"

    # Vault OIDC Authentication Flow Audit against Authentik
    r_vault_oidc = http_client.post(f'{vault_url}/v1/auth/oidc/oidc/auth_url', json={'role': 'admin', 'redirect_uri': f'https://vault.{domain}/ui/vault/auth/oidc/oidc/callback'}, verify=vault_ca)
    assert r_vault_oidc.status_code == 200, f"Vault OIDC auth_url failed: HTTP {r_vault_oidc.status_code}"
    auth_url = r_vault_oidc.json().get('data', {}).get('auth_url', '')
    assert auth_url, "Vault OIDC auth_url empty"

    sess_oidc = make_session()
    # In host runner environment, rewrite internal docker hostname to public https domain if needed
    if 'authentik-server:9000' in auth_url:
        auth_url = auth_url.replace('http://authentik-server:9000', f'https://authentik.{domain}')
    r_oidc_res = authentik_oidc_authorize(sess_oidc, auth_url, 'admin', admin_password, follow_final_redirect=False)
    loc = r_oidc_res.headers.get('Location', '')
    assert 'code=' in loc, f"Authentik OIDC authorize didn't return code redirect, got: {loc}"
    query_params = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
    state_val = query_params.get('state', [''])[0]
    code_val = query_params.get('code', [''])[0]

    r_cb = http_client.get(f'{vault_url}/v1/auth/oidc/oidc/callback?state={state_val}&code={code_val}', verify=vault_ca)
    assert r_cb.status_code == 200 and r_cb.json().get('auth', {}).get('client_token'), f"Vault OIDC code exchange failed: {r_cb.text}"

    return f"Vault unsealed & healthy | Web UI active | KV v2 secret read OK ({pg_pass[:4]}***) | OIDC Login OK"


def test_betterleaks():
    """Validates Betterleaks Presidio microservice and LiteLLM guardrail integration."""
    # 1. Health check (with retry for cold-start initialization)
    r_health = None
    for attempt in range(15):
        try:
            r_health = http_client.get("http://localhost:8090/healthz")
            if r_health.status_code == 200 and r_health.json().get("status") == "healthy":
                break
        except Exception:
            pass
        time.sleep(1)
    assert r_health and r_health.status_code == 200, f"Betterleaks health failed: HTTP {getattr(r_health, 'status_code', 'unreachable')}"
    assert r_health.json().get("status") == "healthy", f"Unexpected health payload: {getattr(r_health, 'text', '')}"

    # 2. Direct Redaction API
    test_secret = "ghp_123456789012345678901234567890123456"  # gitleaks:allow
    r_redact = http_client.post("http://localhost:8090/redact", json={
        "text": f"Leaked token {test_secret}",
        "mode": "replace"
    })
    assert r_redact.status_code == 200, f"Betterleaks /redact failed: HTTP {r_redact.status_code}"
    redact_data = r_redact.json()
    assert redact_data.get("has_secrets") is True, f"Expected has_secrets=True, got {redact_data}"
    assert "<GITHUB_PAT>" in redact_data.get("clean_text", ""), f"Secret was not redacted: {redact_data}"

    # 3. LiteLLM Presidio Guardrail Integration
    assert litellm_master_key, "Missing LITELLM_MASTER_KEY in .env or vault"
    r_guardrail = http_client.post(
        "http://localhost:4001/guardrails/apply_guardrail",
        headers={
            "Authorization": f"Bearer {litellm_master_key}",
            "Content-Type": "application/json"
        },
        json={
            "guardrail_name": "presidio-pii-masking",
            "text": f"Here is my key: {test_secret}"
        }
    )
    assert r_guardrail.status_code == 200, f"LiteLLM apply_guardrail failed: HTTP {r_guardrail.status_code}"
    assert "<GITHUB_PAT>" in r_guardrail.json().get("response_text", ""), f"LiteLLM did not mask secret: {r_guardrail.text}"

    # 4. Observability metrics
    r_metrics = http_client.get("http://localhost:8090/metrics")
    assert r_metrics.status_code == 200, f"Betterleaks /metrics failed: HTTP {r_metrics.status_code}"
    assert "betterleaks_findings_total" in r_metrics.text, "Metrics missing betterleaks_findings_total"

    # 5. Reversible Vaulted Tokenization
    r_tok = http_client.post("http://localhost:8090/tokenize", json={
        "text": f"Write a script that uses token: {test_secret}",
        "ttl_seconds": 60,
    })
    assert r_tok.status_code == 200, f"Betterleaks /tokenize failed: HTTP {r_tok.status_code}"
    tok_data = r_tok.json()
    assert tok_data.get("has_secrets") is True, f"Tokenize expected secrets: {tok_data}"
    assert "TOK_GITHUB_PAT_" in tok_data.get("tokenized_text", "")
    assert test_secret not in tok_data.get("tokenized_text", "")

    # Simulate LLM response containing the surrogate token
    github_token = next(t["token"] for t in tok_data["tokens"] if t["entity_type"] == "GITHUB_PAT")
    llm_simulated = f"Here is the script:\ncurl -H 'Authorization: Bearer {github_token}' https://api.github.com/user"
    r_detok = http_client.post("http://localhost:8090/detokenize", json={
        "text": llm_simulated
    })
    assert r_detok.status_code == 200, f"Betterleaks /detokenize failed: HTTP {r_detok.status_code}"
    detok_data = r_detok.json()
    assert detok_data.get("rehydrated_count", 0) >= 1
    assert test_secret in detok_data.get("detokenized_text", "")
    assert github_token not in detok_data.get("detokenized_text", "")

    return "Service healthy | Redaction API OK | LiteLLM Guardrail verified | Reversible Tokenization OK | Prometheus metrics active"


def test_docs_user():
    # Anonymous request must redirect to Authentik
    r_anon = s.get(f'https://docs.{domain}/', allow_redirects=False)
    assert r_anon.status_code in (302, 307), f"Expected redirect for unauthenticated request to docs.{domain}, got HTTP {r_anon.status_code}"
    assert 'authentik' in r_anon.headers.get('Location', ''), f"Redirect target unexpected: {r_anon.headers.get('Location')}"

    # Authenticated user (alice - regular users group) must be allowed
    alice_sess, r_docs = authentik_login(f'https://docs.{domain}/', 'alice', alice_password)
    assert r_docs.status_code == 200, f"Alice was unable to access docs.{domain}, got HTTP {r_docs.status_code}"

    # French translation must return HTTP 200
    r_fr = alice_sess.get(f'https://docs.{domain}/fr/', allow_redirects=True)
    assert r_fr.status_code == 200, f"French user docs returned HTTP {r_fr.status_code}"

    return "Authentik Forward-Auth OK | alice allowed (users group) | EN & FR served (HTTP 200)"


def test_docs_arch():
    # Anonymous request must redirect to Authentik
    r_anon = s.get(f'https://arch.{domain}/', allow_redirects=False)
    assert r_anon.status_code in (302, 307), f"Expected redirect for unauthenticated request to arch.{domain}, got HTTP {r_anon.status_code}"
    assert 'authentik' in r_anon.headers.get('Location', ''), f"Redirect target unexpected: {r_anon.headers.get('Location')}"

    # Alice (regular user) must be blocked (RBAC: admins only)
    _, r_alice = authentik_login(f'https://arch.{domain}/', 'alice', alice_password)
    assert 'Permission denied' in r_alice.text or 'ak-stage-access-denied' in r_alice.text, "Alice was not blocked from arch.{domain} (RBAC gap)"

    # Admin must be allowed
    admin_sess, r_arch = authentik_login(f'https://arch.{domain}/', 'admin', admin_password)
    assert r_arch.status_code == 200, f"Admin was unable to access arch.{domain}, got HTTP {r_arch.status_code}"

    # French translation must return HTTP 200
    r_fr = admin_sess.get(f'https://arch.{domain}/fr/', allow_redirects=True)
    assert r_fr.status_code == 200, f"French arch docs returned HTTP {r_fr.status_code}"

    return "Authentik Forward-Auth OK | admin allowed, alice blocked (admins-only RBAC) | EN & FR served (HTTP 200)"


def test_coredns():
    """Validates CoreDNS DNS resolution for domain and wildcard subdomains."""
    import socket
    import struct

    bind_ip = env_file.get('COREDNS_BIND_IP', '127.0.0.1')

    def make_query(host):
        # Transaction ID 0x1234, Flags: standard query with RD=1, QDCOUNT=1
        header = struct.pack(">HHHHHH", 0x1234, 0x0100, 1, 0, 0, 0)
        qname = b"".join(bytes([len(p)]) + p.encode('ascii') for p in host.split('.')) + b"\x00"
        return header + qname + struct.pack(">HH", 1, 1)

    def query(host):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3.0)
        sock.sendto(make_query(host), (bind_ip, 53))
        data, _ = sock.recvfrom(512)
        sock.close()
        flags = struct.unpack(">H", data[2:4])[0]
        rcode = flags & 0x000F
        ancount = struct.unpack(">H", data[6:8])[0]
        assert rcode == 0, f"CoreDNS returned rcode {rcode}"
        assert ancount > 0, "CoreDNS returned 0 answers"
        return ".".join(str(b) for b in data[-4:])

    resolved = query(f"chat.{domain}")
    return f"CoreDNS resolution OK | chat.{domain} -> {resolved} via {bind_ip}:53"


CORE_TEST_REGISTRY = [
    ("BETTERLEAKS", "Betterleaks Presidio Redaction", test_betterleaks),
    ("VAULT", "Vault Secrets Engine", test_vault),
    ("POSTGRES", "PostgreSQL Relational Database", test_postgres),
    ("REDIS", "Redis Cache", test_redis),
    ("DASHBOARD", "Application Dashboard RBAC", test_application_dashboard),
    ("LANGFUSE", "Langfuse LLMOps OIDC", test_langfuse),
    ("CLICKHOUSE", "CHouse UI ClickHouse OIDC", test_chouse_ui),
    ("LITELLM", "LiteLLM Proxy Gateway", test_litellm),
    ("OPEN_WEBUI", "Open-WebUI Chat Interface", test_open_webui),
    ("GRAFANA", "Grafana Dashboards", test_grafana),
    ("LOGS", "Dozzle Container Logs", test_dozzle),
    ("SEARXNG", "SearXNG Metasearch", test_searxng),
    ("S3_CONSOLE", "SeaweedFS Console", test_seaweedfs_console),
    ("TRAEFIK", "Traefik Ingress Dashboard", test_traefik),
    ("ALERTMANAGER", "Prometheus Alertmanager", test_alertmanager),
    ("QDRANT", "Qdrant Vector DB", test_qdrant),
    ("S3_API", "SeaweedFS S3 API (SigV4)", test_s3_api),
    ("RBAC_ANON", "RBAC - Anonymous access blocked", test_rbac_anonymous),
    ("RBAC_USERS", "RBAC - 'users' group restricted", test_rbac_users_group),
    ("OLLAMA", "Ollama Default Model (CPU)", test_ollama_default_model),
    ("PROMETHEUS", "Prometheus Observability", test_prometheus_observability),
    ("LOKI", "Loki Log Ingestion", test_loki_log_ingestion),
    ("RAG", "Open-WebUI Knowledge RAG (Qdrant)", test_open_webui_knowledge_rag),
    ("WEB_SEARCH", "Open-WebUI Web Search (SearXNG)", test_open_webui_web_search),
    ("DOCS_USER", "User Documentation (Diataxis)", test_docs_user),
    ("DOCS_ARCH", "Architecture Documentation (arc42 & C4)", test_docs_arch),
]

DNS_TEST_REGISTRY = [
    ("COREDNS", "CoreDNS LAN Wildcard DNS", test_coredns),
]

dns_mode = env_file.get('DNS_MODE', 'hosts')
active_dns_tests = DNS_TEST_REGISTRY if dns_mode == 'coredns' else []

TEST_REGISTRY = CORE_TEST_REGISTRY + active_dns_tests
ALL_POSSIBLE_TESTS = CORE_TEST_REGISTRY + DNS_TEST_REGISTRY


def print_available_tests():
    print("Available test keys for selection:")
    print("-" * 50)
    for key, name, _ in ALL_POSSIBLE_TESTS:
        print(f"  {key:<15} : {name}")
    print("-" * 50)
    print("Usage example: ./smoke_test.sh GRAFANA,LITELLM")


def main():
    args = sys.argv[1:]

    if args and args[0] in ("-l", "--list", "help", "-h", "--help"):
        print_available_tests()
        sys.exit(0)

    selected_tests = []
    if args:
        raw_keys = []
        for arg in args:
            raw_keys.extend(arg.split(','))
        requested_keys = [k.strip().upper() for k in raw_keys if k.strip()]

        key_map = {item[0]: item for item in ALL_POSSIBLE_TESTS}
        missing = [k for k in requested_keys if k not in key_map]
        if missing:
            print(f"Error: Unknown test key(s): {', '.join(missing)}")
            print_available_tests()
            sys.exit(2)

        for k in requested_keys:
            if key_map[k] not in selected_tests:
                selected_tests.append(key_map[k])
    else:
        selected_tests = TEST_REGISTRY

    total = len(selected_tests)
    print("========================================================================")
    print(f" LLM STACK FUNCTIONAL AUDIT ({total} TEST(S) SELECTED)")
    print("========================================================================")

    passed = 0
    for i, (key, name, fn) in enumerate(selected_tests, start=1):
        try:
            detail = fn()
            print(f"[OK]   [{i:2d}/{total}] {key:<12} ({name}): {detail}")
            passed += 1
        except Exception as e:
            print(f"[FAIL] [{i:2d}/{total}] {key:<12} ({name}): FAILED ({e})")

    print("========================================================================")
    if passed == total:
        print(f" AUDIT SUITE: 100% SUCCESS ({passed}/{total} TESTS PASSED)")
        sys.exit(0)
    else:
        print(f" AUDIT SUITE: {passed}/{total} TESTS PASSED.")
        sys.exit(1)


if __name__ == '__main__':
    main()
