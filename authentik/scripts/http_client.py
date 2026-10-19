#!/usr/bin/env python3
"""Small JSON HTTP client implemented with the Python standard library."""

import json
from dataclasses import dataclass
from urllib import error, request


class _NoRedirect(request.HTTPRedirectHandler):
    """Return redirect responses to the caller instead of following them."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: PLR0913
        return None


@dataclass
class Response:
    """Subset of an HTTP response needed by the Authentik provisioners."""

    status_code: int
    headers: object
    body: bytes

    def json(self) -> dict:
        """Decode a JSON response body."""
        return json.loads(self.body.decode("utf-8")) if self.body else {}

    def raise_for_status(self) -> None:
        """Raise when the response is outside the successful HTTP range."""
        if not 200 <= self.status_code < 300:
            raise RuntimeError(
                f"HTTP {self.status_code}: {self.body.decode('utf-8', errors='replace')}"
            )


def request_json(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    payload: dict | None = None,
    timeout: int = 10,
    follow_redirects: bool = True,
) -> Response:
    """Send an HTTP request and return its status, headers, and response body."""
    body = None
    request_headers = dict(headers or {})
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    http_request = request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    opener = request.build_opener() if follow_redirects else request.build_opener(_NoRedirect())
    try:
        with opener.open(http_request, timeout=timeout) as http_response:
            return Response(http_response.status, http_response.headers, http_response.read())
    except error.HTTPError as http_error:
        return Response(http_error.code, http_error.headers, http_error.read())
