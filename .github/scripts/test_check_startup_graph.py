#!/usr/bin/env python3
"""Unit tests for the Docker Compose startup graph validator."""

import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).with_name("check_startup_graph.py")
SPEC = importlib.util.spec_from_file_location("check_startup_graph", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def service(dependencies=None, **properties):
    """Build a minimal resolved Compose service for a validator test."""
    return {"depends_on": dependencies or {}, **properties}


def dependency(condition):
    """Build a resolved Compose dependency condition."""
    return {"condition": condition, "required": True}


class StartupGraphTests(unittest.TestCase):
    def valid_services(self):
        healthcheck = {"test": ["CMD", "ak", "healthcheck"]}
        return {
            "postgres": service(),
            "litellm": service(healthcheck={"start_period": "3m0s"}),
            "authentik-server": service(
                {"postgres": dependency("service_healthy")}, healthcheck=healthcheck
            ),
            "authentik-worker": service(
                {"postgres": dependency("service_healthy")}, healthcheck=healthcheck
            ),
            "authentik-provision": service(
                {
                    "authentik-server": dependency("service_healthy"),
                    "authentik-worker": dependency("service_healthy"),
                },
                profiles=["provisioning"],
                restart="no",
            ),
        }

    def test_valid_contract_is_accepted(self) -> None:
        services = self.valid_services()

        self.assertEqual(MODULE.validate_required_contracts(services), [])
        self.assertEqual(MODULE.validate_acyclic(services), [])

    def test_started_condition_cannot_replace_worker_health(self) -> None:
        services = self.valid_services()
        services["authentik-provision"]["depends_on"]["authentik-worker"] = dependency(
            "service_started"
        )

        errors = MODULE.validate_required_contracts(services)

        self.assertTrue(any("authentik-worker" in error for error in errors))

    def test_litellm_cold_start_grace_period_cannot_be_shortened(self) -> None:
        services = self.valid_services()
        services["litellm"]["healthcheck"]["start_period"] = "2m59s"

        errors = MODULE.validate_required_contracts(services)

        self.assertTrue(any("litellm" in error and "180s" in error for error in errors))

    def test_cycle_is_rejected(self) -> None:
        services = self.valid_services()
        services["postgres"]["depends_on"] = {
            "authentik-provision": dependency("service_started")
        }

        errors = MODULE.validate_acyclic(services)

        self.assertEqual(len(errors), 1)
        self.assertIn("startup dependency cycle", errors[0])


if __name__ == "__main__":
    unittest.main()
