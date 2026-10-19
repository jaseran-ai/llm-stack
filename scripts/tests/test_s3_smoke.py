#!/usr/bin/env python3
"""Fail-closed tests for the signed, scoped SeaweedFS smoke probe."""

from datetime import datetime, timezone
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import s3_smoke


TOKEN = "a" * 32
PAYLOAD = f"llm-stack-s3-smoke:{TOKEN}".encode()


class Response:
    def __init__(self, status_code, content=b""):
        self.status_code = status_code
        self.content = content


class FakeSession:
    def __init__(self, responses, *, verify, timeout):
        self.responses = list(responses)
        self.verify = verify
        self.timeout = timeout
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class S3SmokeTests(unittest.TestCase):
    def run_probe(self, responses, *, tls_ca=None):
        fake = FakeSession(responses, verify=True, timeout=20)
        with mock.patch.object(s3_smoke, "load_credentials", return_value=("access", "private-secret")), \
             mock.patch.object(s3_smoke.secrets, "token_hex", return_value=TOKEN), \
             mock.patch.object(s3_smoke.ssl, "create_default_context") as context_factory, \
             mock.patch.object(s3_smoke.http_client, "Session", return_value=fake) as session:
            result = s3_smoke.probe(
                "example.test", "langfuse", "auto", "unused-s3.json", tls_ca=tls_ca,
            )
            fake.verify = session.call_args.kwargs["verify"]
        return result, fake, context_factory

    def test_signs_payload_hash_and_never_includes_secret_in_headers(self):
        now = datetime(2026, 9, 12, 19, 0, tzinfo=timezone.utc)
        headers = s3_smoke.sign_request(
            "PUT", "s3.example.test", "/langfuse/smoke-tests/a.txt", b"payload",
            "access", "private-secret", "auto", now,
        )
        self.assertEqual(headers["x-amz-content-sha256"], hashlib.sha256(b"payload").hexdigest())
        self.assertEqual(headers["x-amz-date"], "20260912T190000Z")
        self.assertIn("Credential=access/20260912/auto/s3/aws4_request", headers["Authorization"])
        self.assertIn("SignedHeaders=host;x-amz-content-sha256;x-amz-date", headers["Authorization"])
        self.assertNotIn("private-secret", repr(headers))
        other = s3_smoke.sign_request(
            "PUT", "s3.example.test", "/langfuse/smoke-tests/a.txt", b"different",
            "access", "private-secret", "auto", now,
        )
        self.assertNotEqual(headers["Authorization"], other["Authorization"])

    def test_missing_credentials_fail_before_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(s3_smoke.http_client, "Session") as session:
            with self.assertRaisesRegex(RuntimeError, "credential file is missing"):
                s3_smoke.probe("example.test", "langfuse", "auto", pathlib.Path(directory) / "missing.json")
            session.assert_not_called()

    def test_invalid_credentials_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "s3.json"
            path.write_text(json.dumps({"identities": [{"name": "seaweed_admin", "credentials": [
                {"accessKey": "access", "secretKey": ""},
            ]}]}), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "secret key is invalid"):
                s3_smoke.load_credentials(path)

    def test_missing_tls_trust_fails_before_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(s3_smoke, "load_credentials", return_value=("access", "private-secret")), \
             mock.patch.object(s3_smoke.http_client, "Session") as session:
            with self.assertRaisesRegex(RuntimeError, "TLS trust certificate is missing"):
                s3_smoke.probe(
                    "example.test", "langfuse", "auto", "unused-s3.json",
                    tls_ca=pathlib.Path(directory) / "missing.crt",
                )
            session.assert_not_called()

    def test_invalid_tls_trust_fails_before_network(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(s3_smoke, "load_credentials", return_value=("access", "private-secret")), \
             mock.patch.object(s3_smoke.http_client, "Session") as session:
            ca = pathlib.Path(directory) / "invalid.crt"
            ca.write_text("not a certificate", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "TLS trust certificate is invalid"):
                s3_smoke.probe("example.test", "langfuse", "auto", "unused-s3.json", tls_ca=ca)
            session.assert_not_called()

    def test_invalid_bucket_fails_before_reading_credentials(self):
        with mock.patch.object(s3_smoke, "load_credentials") as credentials:
            with self.assertRaisesRegex(RuntimeError, "bucket is invalid"):
                s3_smoke.probe("example.test", "../other-bucket", "auto", "unused-s3.json")
            credentials.assert_not_called()

    def test_success_round_trip_uses_verified_tls_and_scoped_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            ca = pathlib.Path(directory) / "tls.crt"
            ca.write_text("test certificate", encoding="utf-8")
            result, fake, context_factory = self.run_probe(
                [Response(404), Response(200), Response(200, PAYLOAD), Response(204)], tls_ca=ca,
            )
        self.assertIn("SigV4 PUT/GET", result)
        self.assertIs(fake.verify, context_factory.return_value)
        context_factory.assert_called_once_with()
        context_factory.return_value.load_verify_locations.assert_called_once_with(cafile=str(ca))
        self.assertEqual([call[0] for call in fake.calls], ["HEAD", "PUT", "GET", "DELETE"])
        self.assertEqual(len({call[1] for call in fake.calls}), 1)
        self.assertTrue(fake.calls[0][1].endswith(f"/langfuse/smoke-tests/{TOKEN}.txt"))
        self.assertEqual(fake.calls[1][2]["data"], PAYLOAD)
        self.assertTrue(all(call[2]["allow_redirects"] is False for call in fake.calls))
        self.assertNotIn("private-secret", repr(fake.calls))

    def test_public_tls_path_uses_system_trust(self):
        result, fake, context_factory = self.run_probe(
            [Response(404), Response(200), Response(200, PAYLOAD), Response(204)],
        )
        self.assertIn("SigV4 PUT/GET", result)
        self.assertIs(fake.verify, True)
        context_factory.assert_not_called()

    def test_existing_object_is_never_overwritten_or_deleted(self):
        fake = FakeSession([Response(200)], verify=True, timeout=20)
        with mock.patch.object(s3_smoke, "load_credentials", return_value=("access", "private-secret")), \
             mock.patch.object(s3_smoke.secrets, "token_hex", return_value=TOKEN), \
             mock.patch.object(s3_smoke.http_client, "Session", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "precheck returned HTTP 200"):
                s3_smoke.probe("example.test", "langfuse", "auto", "unused-s3.json")
        self.assertEqual([call[0] for call in fake.calls], ["HEAD"])

    def test_failed_put_attempts_cleanup(self):
        fake = FakeSession([Response(404), Response(500), Response(204)], verify=True, timeout=20)
        with mock.patch.object(s3_smoke, "load_credentials", return_value=("access", "private-secret")), \
             mock.patch.object(s3_smoke.secrets, "token_hex", return_value=TOKEN), \
             mock.patch.object(s3_smoke.http_client, "Session", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "Signed S3 PUT returned HTTP 500"):
                s3_smoke.probe("example.test", "langfuse", "auto", "unused-s3.json")
        self.assertEqual([call[0] for call in fake.calls], ["HEAD", "PUT", "DELETE"])

    def test_payload_mismatch_fails_after_cleanup(self):
        fake = FakeSession(
            [Response(404), Response(200), Response(200, b"wrong"), Response(204)],
            verify=True, timeout=20,
        )
        with mock.patch.object(s3_smoke, "load_credentials", return_value=("access", "private-secret")), \
             mock.patch.object(s3_smoke.secrets, "token_hex", return_value=TOKEN), \
             mock.patch.object(s3_smoke.http_client, "Session", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "payload does not match"):
                s3_smoke.probe("example.test", "langfuse", "auto", "unused-s3.json")
        self.assertEqual([call[0] for call in fake.calls], ["HEAD", "PUT", "GET", "DELETE"])

    def test_failed_cleanup_fails_the_probe(self):
        fake = FakeSession(
            [Response(404), Response(200), Response(200, PAYLOAD), Response(500)],
            verify=True, timeout=20,
        )
        with mock.patch.object(s3_smoke, "load_credentials", return_value=("access", "private-secret")), \
             mock.patch.object(s3_smoke.secrets, "token_hex", return_value=TOKEN), \
             mock.patch.object(s3_smoke.http_client, "Session", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "cleanup returned HTTP 500"):
                s3_smoke.probe("example.test", "langfuse", "auto", "unused-s3.json")


if __name__ == "__main__":
    unittest.main()
