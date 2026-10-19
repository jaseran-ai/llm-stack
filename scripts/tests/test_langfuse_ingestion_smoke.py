"""Fail-closed checks for the attested Langfuse ingestion probes."""

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'smoke_test.py'
sys.path.insert(0, str(SCRIPT.parent))


class Response:
    def __init__(self, status_code, data=None, *, url='', text='', headers=None):
        self.status_code = status_code
        self._data = data
        self.url = url
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._data


class Client:
    def __init__(self):
        self.ingestion_status = 207
        self.s3_status = 200
        self.event = None
        self.s3_gets = 0

    def post(self, url, **kwargs):
        self.event = kwargs['json']['batch'][0]
        return Response(
            self.ingestion_status,
            {'successes': [{'id': self.event['id'], 'status': 201}], 'errors': []},
        )

    def get(self, url, **kwargs):
        self.s3_gets += 1
        return Response(self.s3_status, [self.event])


class WebSession:
    def get(self, url, **kwargs):
        if url.endswith('/api/auth/csrf'):
            return Response(200, {'csrfToken': 'token'})
        if url.endswith('/api/auth/session'):
            return Response(200, text='admin@example.com')
        if url.endswith('/api/public/projects'):
            return Response(200, {'data': [{'name': 'project'}]})
        raise AssertionError('Unexpected Langfuse GET endpoint')

    def post(self, url, **kwargs):
        if url.endswith('/api/auth/signin/custom'):
            return Response(302, headers={'Location': 'https://authentik.example.test/authorize'})
        raise AssertionError('Unexpected Langfuse POST endpoint')


class LangfuseIngestionSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        original_dir = os.getcwd()
        try:
            os.chdir(cls.temp.name)
            Path('.env').write_text(
                'DOMAIN=example.test\n'
                'UI_PASSWORD=test\n'
                'ALICE_PASSWORD=test\n'
                'BOB_PASSWORD=test\n'
                'LANGFUSE_INIT_PROJECT_PUBLIC_KEY=test\n'
                'LANGFUSE_INIT_PROJECT_SECRET_KEY=test\n'
                'LANGFUSE_INIT_PROJECT_ID=project123\n'
                'LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse\n'
                'LANGFUSE_S3_EVENT_UPLOAD_PREFIX=events/\n'
                'LANGFUSE_S3_EVENT_UPLOAD_REGION=auto\n'
                'CLICKHOUSE_PASSWORD=test\n'
                'TLS_MODE=internal\n',
                encoding='utf-8',
            )
            spec = importlib.util.spec_from_file_location('smoke_test_unit', SCRIPT)
            cls.smoke = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.smoke)
        finally:
            os.chdir(original_dir)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.client = Client()

    def run_probe(self, client=None, *, environment='uat'):
        client = client or self.client
        with mock.patch.dict(os.environ, {
                 'SMOKE_ENVIRONMENT': environment,
                 'SMOKE_UAT_IDENTITY_FILE': '/tmp/uat-identity' if environment == 'uat' else '',
                 'SMOKE_PROD_LANGFUSE_INGESTION': '1' if environment == 'production' else '',
             }), \
             mock.patch.object(self.smoke.os.path, 'isfile', return_value=True), \
             mock.patch.object(self.smoke.os.path, 'islink', return_value=False), \
             mock.patch.object(self.smoke.ssl, 'create_default_context') as tls, \
             mock.patch.object(self.smoke.http_client, 'Session', return_value=client), \
             mock.patch.object(self.smoke.http_client, 'get', return_value=Response(200, {'data': [{'matches': 1}]})) as ch_get, \
             mock.patch.object(self.smoke.s3_smoke, 'load_credentials', return_value=('access', 'secret')), \
             mock.patch.object(self.smoke.s3_smoke, 'sign_request', return_value={'Host': 's3.example.test'}), \
             mock.patch.object(self.smoke.time, 'sleep'):
            detail = self.smoke.test_langfuse_ingestion(environment)
        return detail, tls, ch_get

    def test_success_checks_ingestion_s3_and_clickhouse(self):
        detail, tls, ch_get = self.run_probe()
        self.assertIn('HTTP 207', detail)
        self.assertIn('S3 GET 200', detail)
        self.assertIn('ClickHouse trace 1', detail)
        self.assertEqual(self.client.s3_gets, 1)
        self.assertEqual(self.client.event['type'], 'trace-create')
        tls.return_value.load_verify_locations.assert_called_once_with(cafile='traefik/certs/tls.crt')
        ch_get.assert_called_once()

    def test_ingestion_rejection_stops_before_s3(self):
        self.client.ingestion_status = 500
        with self.assertRaisesRegex(RuntimeError, 'ingestion HTTP 500'):
            self.run_probe()
        self.assertEqual(self.client.s3_gets, 0)

    def test_s3_rejection_stops_before_clickhouse(self):
        self.client.s3_status = 403
        with self.assertRaisesRegex(RuntimeError, 'S3 event GET HTTP 403'):
            self.run_probe()

    def test_missing_uat_identity_fails_before_network(self):
        with mock.patch.dict(os.environ, {'SMOKE_UAT_IDENTITY_FILE': ''}), \
             mock.patch.object(self.smoke.http_client, 'Session') as session:
            with self.assertRaisesRegex(RuntimeError, 'UAT identity file'):
                self.smoke.test_langfuse_ingestion('uat')
        session.assert_not_called()

    def test_production_probe_uses_verified_dual_trust(self):
        detail, tls, ch_get = self.run_probe(environment='production')
        self.assertIn('PRODUCTION ingestion HTTP 207', detail)
        self.assertEqual(self.client.event['body']['name'], 'llm-stack-production-ingestion-smoke')
        tls.return_value.load_verify_locations.assert_called_once_with(cafile='traefik/certs/tls.crt')
        ch_get.assert_called_once()

    def test_production_probe_uses_system_trust_for_public_tls(self):
        with mock.patch.dict(self.smoke.env_file, {'TLS_MODE': 'cloudflare-dns01'}):
            detail, tls, _ = self.run_probe(environment='production')
        self.assertIn('PRODUCTION ingestion HTTP 207', detail)
        tls.return_value.load_verify_locations.assert_not_called()

    def test_production_probe_requires_explicit_attestation_before_network(self):
        with mock.patch.dict(os.environ, {
                 'SMOKE_ENVIRONMENT': 'production',
                 'SMOKE_PROD_LANGFUSE_INGESTION': '',
                 'SMOKE_UAT_IDENTITY_FILE': '',
             }), mock.patch.object(self.smoke.http_client, 'Session') as session:
            with self.assertRaisesRegex(RuntimeError, 'explicit production attestation'):
                self.smoke.test_langfuse_ingestion('production')
        session.assert_not_called()

    def test_unsupported_tls_mode_fails_before_network(self):
        with mock.patch.dict(self.smoke.env_file, {'TLS_MODE': 'unknown'}), \
             mock.patch.dict(os.environ, {
                 'SMOKE_ENVIRONMENT': 'production',
                 'SMOKE_PROD_LANGFUSE_INGESTION': '1',
                 'SMOKE_UAT_IDENTITY_FILE': '',
             }), mock.patch.object(self.smoke.http_client, 'Session') as session:
            with self.assertRaisesRegex(RuntimeError, 'Unsupported Langfuse ingestion TLS mode'):
                self.smoke.test_langfuse_ingestion('production')
        session.assert_not_called()

    def test_production_langfuse_check_never_writes_synthetic_event(self):
        auth_results = [
            Response(200, url='https://langfuse.example.test/'),
            Response(403, text='Permission denied'),
        ]
        with mock.patch.dict(os.environ, {
                 'SMOKE_ENVIRONMENT': 'production',
                 'SMOKE_PROD_LANGFUSE_INGESTION': '',
             }), \
             mock.patch.object(self.smoke, 'make_session', side_effect=[WebSession(), WebSession()]), \
             mock.patch.object(self.smoke, 'authentik_oidc_authorize', side_effect=auth_results), \
             mock.patch.object(self.smoke, 'test_langfuse_ingestion') as ingestion:
            detail = self.smoke.test_langfuse()
        self.assertIn('Projects API OK', detail)
        ingestion.assert_not_called()

    def test_production_langfuse_check_with_opt_in_calls_probe(self):
        auth_results = [
            Response(200, url='https://langfuse.example.test/'),
            Response(403, text='Permission denied'),
        ]
        with mock.patch.dict(os.environ, {
                 'SMOKE_ENVIRONMENT': 'production',
                 'SMOKE_PROD_LANGFUSE_INGESTION': '1',
             }), \
             mock.patch.object(self.smoke, 'make_session', side_effect=[WebSession(), WebSession()]), \
             mock.patch.object(self.smoke, 'authentik_oidc_authorize', side_effect=auth_results), \
             mock.patch.object(self.smoke, 'test_langfuse_ingestion', return_value='PRODUCTION ingestion OK') as ingestion:
            detail = self.smoke.test_langfuse()
        self.assertIn('PRODUCTION ingestion OK', detail)
        ingestion.assert_called_once_with('production')

    def test_production_opt_in_with_uat_environment_fails_before_network(self):
        with mock.patch.dict(os.environ, {
                 'SMOKE_ENVIRONMENT': 'uat',
                 'SMOKE_PROD_LANGFUSE_INGESTION': '1',
             }), mock.patch.object(self.smoke, 'make_session') as session:
            with self.assertRaisesRegex(RuntimeError, 'requires SMOKE_ENVIRONMENT=production'):
                self.smoke.test_langfuse()
        session.assert_not_called()


if __name__ == '__main__':
    unittest.main()
