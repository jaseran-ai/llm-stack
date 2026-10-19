#!/usr/bin/env python3
"""Validate the declarative Docker Compose startup dependency graph."""

import json
import re
import sys
from typing import Dict, List, Optional


REQUIRED_DEPENDENCIES = {
    "authentik-server": {"postgres": "service_healthy"},
    "authentik-worker": {"postgres": "service_healthy"},
    "authentik-provision": {
        "authentik-server": "service_healthy",
        "authentik-worker": "service_healthy",
    },
}
LITELLM_MINIMUM_START_PERIOD_SECONDS = 180
_DURATION_TOKEN = re.compile(r"(\d+(?:\.\d+)?)(ns|us|ms|s|m|h)")
_DURATION_UNITS = {
    "ns": 0.000000001,
    "us": 0.000001,
    "ms": 0.001,
    "s": 1,
    "m": 60,
    "h": 3600,
}


def parse_compose_duration_seconds(value: object) -> Optional[float]:
    """Return seconds for a resolved Compose duration, or None when invalid."""
    if not isinstance(value, str) or not value:
        return None
    position = 0
    total = 0.0
    for match in _DURATION_TOKEN.finditer(value):
        if match.start() != position:
            return None
        total += float(match.group(1)) * _DURATION_UNITS[match.group(2)]
        position = match.end()
    return total if position == len(value) else None


def validate_required_contracts(services: Dict) -> List[str]:
    """Return errors for missing services, health checks, profiles, or edges."""
    errors = []
    for service_name, required_dependencies in REQUIRED_DEPENDENCIES.items():
        service = services.get(service_name)
        if service is None:
            errors.append(f"missing required service: {service_name}")
            continue
        dependencies = service.get("depends_on", {})
        for dependency_name, expected_condition in required_dependencies.items():
            actual_condition = dependencies.get(dependency_name, {}).get("condition")
            if actual_condition != expected_condition:
                errors.append(
                    f"{service_name} -> {dependency_name}: expected "
                    f"{expected_condition}, got {actual_condition}"
                )

    for service_name in ("authentik-server", "authentik-worker"):
        healthcheck = services.get(service_name, {}).get("healthcheck", {})
        if healthcheck.get("test") != ["CMD", "ak", "healthcheck"]:
            errors.append(f"{service_name}: missing explicit ak healthcheck")

    litellm_start_period = parse_compose_duration_seconds(
        services.get("litellm", {}).get("healthcheck", {}).get("start_period")
    )
    if (
        litellm_start_period is None
        or litellm_start_period < LITELLM_MINIMUM_START_PERIOD_SECONDS
    ):
        errors.append(
            "litellm: healthcheck start_period must be at least "
            f"{LITELLM_MINIMUM_START_PERIOD_SECONDS}s for clean database migrations"
        )

    provision = services.get("authentik-provision", {})
    if provision.get("profiles") != ["provisioning"]:
        errors.append("authentik-provision: must remain opt-in via the provisioning profile")
    if provision.get("restart") != "no":
        errors.append("authentik-provision: restart policy must be no")
    return errors


def validate_acyclic(services: Dict) -> List[str]:
    """Return an error when the Compose dependency graph contains a cycle."""
    visiting = set()
    visited = set()

    def visit(service_name: str, path: List[str]) -> Optional[List[str]]:
        if service_name in visiting:
            cycle_start = path.index(service_name)
            return path[cycle_start:] + [service_name]
        if service_name in visited:
            return None

        visiting.add(service_name)
        path.append(service_name)
        for dependency_name in services.get(service_name, {}).get("depends_on", {}):
            cycle = visit(dependency_name, path)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(service_name)
        visited.add(service_name)
        return None

    for service_name in services:
        cycle = visit(service_name, [])
        if cycle:
            return [f"startup dependency cycle: {' -> '.join(cycle)}"]
    return []


def main() -> int:
    """Read resolved Compose JSON from stdin and validate its startup graph."""
    compose = json.load(sys.stdin)
    services = compose.get("services", {})
    errors = validate_required_contracts(services) + validate_acyclic(services)
    if errors:
        for validation_error in errors:
            print(f"ERROR: {validation_error}", file=sys.stderr)
        return 1
    print(f"Startup dependency graph is valid ({len(services)} services, no cycles).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
