#!/usr/bin/env python3
"""Shared helper: drive Authentik's real flow-executor to complete a login.

Extracted so the exact same, already-validated mechanism (used by smoke_test.sh's own
authentik_oidc_authorize()) has a single source of truth for provisioning scripts that
need it too - litellm/scripts/provision.py imports this instead of keeping its own copy
of the flow-executor driving logic. (smoke_test.sh keeps its own copy rather than importing
this: it deliberately keeps the flow steps local while using the repository's shared
standard-library HTTP client.)

It drives Authentik's real /api/v3/flows/executor/ endpoint (what a real browser's
flow-executor JS does), so automated logins follow exactly the same path as interactive ones.
"""

import urllib.parse


class OidcLoginError(RuntimeError):
    """Raised when any step of the Authentik flow-executor login sequence fails."""


def oidc_authorize(sess, authorize_url, domain, username, password, timeout=15, follow_final_redirect=True):
    """
    Drives Authentik's flow-executor to complete a login starting from an arbitrary
    /application/o/authorize/ URL (i.e. one issued by an app's own native OIDC client, e.g.
    NextAuth's /api/auth/signin/<provider> or LiteLLM's /sso/key/generate). Returns the final
    response after following the app's OAuth callback redirect (allow_redirects=True by
    default), so the app's own session cookie ends up set on `sess`.

    follow_final_redirect=False returns the raw redirect response instead (Location header
    intact, not followed) - needed for apps whose OAuth callback is a plain redirect carrying a
    code/state query string that the caller itself must POST elsewhere (e.g. CHouse UI, see
    smoke_test.sh's test_chouse_ui()).

    Raises OidcLoginError (never silently returns a half-completed session) if any expected
    step of the flow doesn't look like a real Authentik login flow - callers are expected to
    catch this alongside network-level exceptions.
    """
    if not authorize_url:
        raise OidcLoginError("no authorize_url provided (upstream redirect was missing)")

    r = sess.get(authorize_url, allow_redirects=True, timeout=timeout)
    if "/if/flow/" not in r.url:
        raise OidcLoginError(f"expected an Authentik login flow redirect, got {r.url}")
    flow_slug = r.url.split("/if/flow/")[1].split("/")[0]
    query = r.url.split("?", 1)[1] if "?" in r.url else ""
    next_param = urllib.parse.parse_qs(query).get("next", [None])[0]
    if not next_param:
        raise OidcLoginError(f"no 'next' OAuth continuation param in {r.url}")

    exec_url = f"https://authentik.{domain}/api/v3/flows/executor/{flow_slug}/?query={query}"
    sess.post(exec_url, json={"uid_field": username}, timeout=timeout)
    sess.post(exec_url, json={"password": password}, timeout=timeout)
    for _ in range(5):
        r_poll = sess.get(exec_url, timeout=timeout)
        data = r_poll.json()
        if data.get("component") != "xak-flow-redirect" or data.get("final_redirect"):
            break

    next_url = f"https://authentik.{domain}" + urllib.parse.unquote(next_param)
    return sess.get(next_url, allow_redirects=follow_final_redirect, timeout=timeout)
