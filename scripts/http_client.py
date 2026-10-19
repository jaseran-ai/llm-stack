#!/usr/bin/env python3
"""Small synchronous HTTP client built entirely on the Python standard library."""

import base64
import gzip
import http.cookiejar
import json as json_module
import secrets
import ssl
import urllib.error
import urllib.parse
import urllib.request
import zlib


_URI_SAFE_CHARACTERS = "!#$%&'()*+,/:;=?@[]~"
DEFAULT_USER_AGENT = "llm-stack-automation/1.0"


class HttpStatusError(RuntimeError):
    """Raised by Response.raise_for_status for an HTTP error response."""

    def __init__(self, response):
        super().__init__(f"HTTP {response.status_code} for {response.url}: {response.text[:200]}")
        self.response = response


class Response:
    """Buffered HTTP response with the subset used by stack automation."""

    def __init__(self, status_code, headers, content, url):
        self.status_code = status_code
        self.headers = headers
        encoding = (headers.get("Content-Encoding") or "").lower() if hasattr(headers, "get") else ""
        if encoding == "gzip":
            try:
                content = gzip.decompress(content)
            except Exception:
                pass
        elif encoding == "deflate":
            try:
                content = zlib.decompress(content)
            except Exception:
                pass
        self.content = content
        self.url = url

    @property
    def text(self):
        charset = self.headers.get_content_charset() if hasattr(self.headers, "get_content_charset") else None
        return self.content.decode(charset or "utf-8", errors="replace")

    def json(self):
        return json_module.loads(self.content.decode("utf-8"))

    def raise_for_status(self):
        if 400 <= self.status_code:
            raise HttpStatusError(self)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _normalize_url(url):
    """Percent-encode unsafe characters while preserving valid URI delimiters and escapes."""
    return urllib.parse.quote(url, safe=_URI_SAFE_CHARACTERS)


def _tls_context(verify):
    if isinstance(verify, ssl.SSLContext):
        if not verify.check_hostname or verify.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("TLS context must verify certificates and hostnames")
        return verify
    if verify is True:
        return ssl.create_default_context()
    if isinstance(verify, str):
        return ssl.create_default_context(cafile=verify)
    if verify is False:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    raise TypeError("TLS verification must be a boolean, CA file path, or SSLContext")


def _multipart_body(files, data):
    boundary = f"----llm-stack-{secrets.token_hex(16)}"
    chunks = []

    for name, value in (data or {}).items():
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode(),
            b"\r\n",
        ])

    for name, file_spec in files.items():
        filename, file_object, content_type = file_spec
        file_content = file_object.read() if hasattr(file_object, "read") else file_object
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            file_content,
            b"\r\n",
        ])

    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


class Session:
    """Cookie-aware HTTP session with explicit TLS and timeout policy."""

    def __init__(self, *, verify=True, timeout=None):
        self.verify = verify
        self.timeout = timeout
        self.cookies = http.cookiejar.CookieJar()

    def _opener(self, allow_redirects, verify):
        handlers = [
            urllib.request.HTTPCookieProcessor(self.cookies),
            urllib.request.HTTPSHandler(context=_tls_context(verify)),
        ]
        if not allow_redirects:
            handlers.append(_NoRedirect())
        return urllib.request.build_opener(*handlers)

    def request(
        self,
        method,
        url,
        *,
        headers=None,
        params=None,
        data=None,
        json=None,
        files=None,
        auth=None,
        timeout=None,
        allow_redirects=True,
        verify=None,
    ):
        if params:
            query = urllib.parse.urlencode(params, doseq=True)
            url = f"{url}{'&' if urllib.parse.urlsplit(url).query else '?'}{query}"

        request_headers = dict(headers or {})
        request_headers.setdefault("User-Agent", DEFAULT_USER_AGENT)
        request_headers.setdefault("Accept-Encoding", "gzip, deflate")
        if auth:
            credentials = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            request_headers["Authorization"] = f"Basic {credentials}"

        body = None
        if files is not None:
            body, content_type = _multipart_body(files, data)
            request_headers.setdefault("Content-Type", content_type)
        elif json is not None:
            body = json_module.dumps(json, separators=(",", ":")).encode()
            request_headers.setdefault("Content-Type", "application/json")
        elif isinstance(data, dict):
            body = urllib.parse.urlencode(data, doseq=True).encode()
            request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
        elif isinstance(data, str):
            body = data.encode()
        elif data is not None:
            body = data

        req = urllib.request.Request(_normalize_url(url), data=body, headers=request_headers, method=method.upper())
        effective_verify = self.verify if verify is None else verify
        try:
            raw = self._opener(allow_redirects, effective_verify).open(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as error:
            raw = error
        content = raw.read()
        return Response(raw.status, raw.headers, content, raw.geturl())

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


def request(method, url, **kwargs):
    verify = kwargs.pop("verify", True)
    timeout = kwargs.pop("timeout", None)
    return Session(verify=verify, timeout=timeout).request(method, url, **kwargs)


def get(url, **kwargs):
    return request("GET", url, **kwargs)


def post(url, **kwargs):
    return request("POST", url, **kwargs)


def put(url, **kwargs):
    return request("PUT", url, **kwargs)


def delete(url, **kwargs):
    return request("DELETE", url, **kwargs)
