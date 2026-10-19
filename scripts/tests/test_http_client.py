#!/usr/bin/env python3
"""Unit tests for the standard-library HTTP client."""

import http.server
import json
import pathlib
import ssl
import sys
import threading
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))

import http_client


class Handler(http.server.BaseHTTPRequestHandler):
    def _reply(self, status, body=b"", headers=None):
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/redirect":
            self._reply(302, headers={"Location": "/final", "Set-Cookie": "flow=ready; Path=/"})
        elif self.path == "/final":
            self._reply(200, self.headers.get("Cookie", "").encode())
        elif self.path.startswith("/query?"):
            self._reply(200, self.path.encode())
        elif self.path == "/headers":
            response = json.dumps({"user_agent": self.headers.get("User-Agent")}).encode()
            self._reply(200, response, {"Content-Type": "application/json; charset=utf-8"})
        else:
            self._reply(404, b"missing")

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        response = json.dumps({
            "content_type": self.headers.get("Content-Type"),
            "authorization": self.headers.get("Authorization"),
            "body": body.decode("latin1"),
        }).encode()
        self._reply(200, response, {"Content-Type": "application/json; charset=utf-8"})

    def log_message(self, _format, *_args):
        pass


class HttpClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_redirect_policy_and_cookie_session(self):
        session = http_client.Session(timeout=2)
        redirect = session.get(f"{self.base}/redirect", allow_redirects=False)
        self.assertEqual(redirect.status_code, 302)
        self.assertEqual(redirect.headers.get("Location"), "/final")
        final = session.get(f"{self.base}/final")
        self.assertEqual(final.text, "flow=ready")

    def test_query_json_form_and_basic_auth(self):
        query = http_client.get(f"{self.base}/query", params={"item": ["a", "b"]}, timeout=2)
        self.assertEqual(query.text, "/query?item=a&item=b")
        json_response = http_client.post(f"{self.base}/echo", json={"ok": True}, auth=("key", "secret"), timeout=2)
        self.assertEqual(json_response.json()["body"], '{"ok":true}')
        self.assertEqual(json_response.json()["authorization"], "Basic a2V5OnNlY3JldA==")
        form_response = http_client.post(f"{self.base}/echo", data={"name": "A B"}, timeout=2)
        self.assertEqual(form_response.json()["body"], "name=A+B")

    def test_unsafe_url_characters_are_percent_encoded(self):
        response = http_client.get(f"{self.base}/query?scope=openid email%20profile", timeout=2)
        self.assertEqual(response.text, "/query?scope=openid%20email%20profile")

    def test_default_user_agent_and_explicit_override(self):
        default_response = http_client.get(f"{self.base}/headers", timeout=2)
        self.assertEqual(default_response.json()["user_agent"], http_client.DEFAULT_USER_AGENT)

        custom_response = http_client.get(
            f"{self.base}/headers",
            headers={"User-Agent": "custom-client/2.0"},
            timeout=2,
        )
        self.assertEqual(custom_response.json()["user_agent"], "custom-client/2.0")

    def test_multipart_and_http_error_response(self):
        upload = http_client.post(
            f"{self.base}/upload",
            files={"file": ("sample.txt", b"payload", "text/plain")},
            timeout=2,
        ).json()
        self.assertIn("multipart/form-data; boundary=", upload["content_type"])
        self.assertIn('filename="sample.txt"', upload["body"])
        self.assertIn("payload", upload["body"])

        missing = http_client.get(f"{self.base}/missing", timeout=2)
        self.assertEqual(missing.status_code, 404)
        with self.assertRaises(http_client.HttpStatusError):
            missing.raise_for_status()

    def test_tls_verification_policy(self):
        verified = http_client._tls_context(True)
        self.assertTrue(verified.check_hostname)
        self.assertEqual(verified.verify_mode, ssl.CERT_REQUIRED)
        self.assertIs(http_client._tls_context(verified), verified)

        insecure = ssl.create_default_context()
        insecure.check_hostname = False
        insecure.verify_mode = ssl.CERT_NONE
        with self.assertRaisesRegex(ValueError, "verify certificates and hostnames"):
            http_client._tls_context(insecure)

        with self.assertRaisesRegex(TypeError, "TLS verification must be"):
            http_client._tls_context(pathlib.Path("tls.crt"))

        local_only = http_client._tls_context(False)
        self.assertFalse(local_only.check_hostname)
        self.assertEqual(local_only.verify_mode, ssl.CERT_NONE)


if __name__ == "__main__":
    unittest.main()
