#!/usr/bin/env python3
"""Exercise one scoped S3 object with Vault credentials and signed requests."""

from datetime import datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import re
import secrets
import ssl

import http_client


SIGNED_HEADERS = "host;x-amz-content-sha256;x-amz-date"


def load_credentials(path):
    """Read the SeaweedFS admin identity from Vault Agent's RAM rendering."""
    secret_file = Path(path)
    if secret_file.is_symlink() or not secret_file.is_file():
        raise RuntimeError("Vault-rendered SeaweedFS S3 credential file is missing or unsafe")
    try:
        with secret_file.open(encoding="utf-8") as handle:
            identities = json.load(handle)["identities"]
        matching = [identity for identity in identities if identity.get("name") == "seaweed_admin"]
        if len(matching) != 1 or len(matching[0]["credentials"]) != 1:
            raise ValueError("unexpected SeaweedFS identity count")
        credential = matching[0]["credentials"][0]
        access_key = credential["accessKey"]
        secret_key = credential["secretKey"]
    except (AttributeError, IndexError, OSError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError("Vault-rendered SeaweedFS S3 credentials are invalid") from error
    if not isinstance(access_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", access_key):
        raise RuntimeError("SeaweedFS S3 access key is invalid")
    if not isinstance(secret_key, str) or not secret_key or "\n" in secret_key or "\r" in secret_key:
        raise RuntimeError("SeaweedFS S3 secret key is invalid")
    return access_key, secret_key


def sign_request(method, host, path, body, access_key, secret_key, region, now):
    """Sign one path-style, query-free S3 request using AWS Signature V4."""
    timestamp = now.strftime("%Y%m%dT%H%M%SZ")
    date = timestamp[:8]
    scope = f"{date}/{region}/s3/aws4_request"
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_headers = (
        f"host:{host}\n"
        f"x-amz-content-sha256:{payload_hash}\n"
        f"x-amz-date:{timestamp}\n"
    )
    canonical_request = "\n".join(
        (method, path, "", canonical_headers, SIGNED_HEADERS, payload_hash)
    )
    string_to_sign = "\n".join((
        "AWS4-HMAC-SHA256", timestamp, scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ))
    signing_key = ("AWS4" + secret_key).encode()
    for component in (date, region, "s3", "aws4_request"):
        signing_key = hmac.new(signing_key, component.encode(), hashlib.sha256).digest()
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return {
        "Host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": timestamp,
        "Authorization": (
            f"AWS4-HMAC-SHA256 Credential={access_key}/{scope},"
            f"SignedHeaders={SIGNED_HEADERS},Signature={signature}"
        ),
    }


def probe(domain, bucket, region, credential_file, *, tls_ca=None):
    """Verify a signed PUT/GET round trip and remove only its own object."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*[a-z0-9]", domain) or ".." in domain:
        raise RuntimeError("S3 smoke domain is invalid")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket) or ".." in bucket:
        raise RuntimeError("S3 smoke bucket is invalid")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,32}", region):
        raise RuntimeError("S3 smoke region is invalid")
    access_key, secret_key = load_credentials(credential_file)
    verify = True
    if tls_ca is not None:
        ca_file = Path(tls_ca)
        if ca_file.is_symlink() or not ca_file.is_file():
            raise RuntimeError("S3 TLS trust certificate is missing or unsafe")
        verify = ssl.create_default_context()
        try:
            verify.load_verify_locations(cafile=str(ca_file))
        except OSError as error:
            raise RuntimeError("S3 TLS trust certificate is invalid") from error

    host = f"s3.{domain}"
    token = secrets.token_hex(16)
    path = f"/{bucket}/smoke-tests/{token}.txt"
    url = f"https://{host}{path}"
    payload = f"llm-stack-s3-smoke:{token}".encode()
    client = http_client.Session(verify=verify, timeout=20)

    def request(method, body=b""):
        headers = sign_request(
            method, host, path, body, access_key, secret_key, region,
            datetime.now(timezone.utc),
        )
        return client.request(
            method, url, headers=headers, data=body if method == "PUT" else None,
            allow_redirects=False,
        )

    head = request("HEAD")
    if head.status_code != 404:
        raise RuntimeError(f"S3 probe object precheck returned HTTP {head.status_code}")

    attempted_put = False
    put_succeeded = False
    try:
        attempted_put = True
        put = request("PUT", payload)
        if put.status_code not in (200, 201):
            raise RuntimeError(f"Signed S3 PUT returned HTTP {put.status_code}")
        put_succeeded = True
        get = request("GET")
        if get.status_code != 200:
            raise RuntimeError(f"Signed S3 GET returned HTTP {get.status_code}")
        if get.content != payload:
            raise RuntimeError("Signed S3 GET payload does not match PUT payload")
    finally:
        if attempted_put:
            deleted = request("DELETE")
            allowed = (200, 204) if put_succeeded else (200, 204, 404)
            if deleted.status_code not in allowed:
                raise RuntimeError(f"S3 probe object cleanup returned HTTP {deleted.status_code}")
    return "SigV4 PUT/GET payload match and scoped DELETE OK"
