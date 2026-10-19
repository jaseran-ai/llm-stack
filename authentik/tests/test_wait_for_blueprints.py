#!/usr/bin/env python3
"""Unit tests for serialized Authentik blueprint recovery."""

import importlib.util
import pathlib
import sys
import unittest
from unittest import mock

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "wait_for_blueprints.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("wait_for_blueprints", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Response:
    """Minimal successful requests response used by the tests."""

    def raise_for_status(self) -> None:
        return None


class BlueprintProvisioningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sleep = mock.patch.object(MODULE.time, "sleep").start()
        self.addCleanup(mock.patch.stopall)

    def test_retry_call_recovers_from_temporary_api_failure(self) -> None:
        operation = mock.Mock(side_effect=[RuntimeError("503"), {"pk": ("name", "successful")}])

        result = MODULE.retry_call(operation, 2, "API")

        self.assertEqual(result, {"pk": ("name", "successful")})
        self.assertEqual(operation.call_count, 2)

    def test_blueprints_are_applied_strictly_one_at_a_time(self) -> None:
        events = []

        def post(_method, url, **_kwargs):
            events.append(("post", url.rsplit("/", 3)[1]))
            return Response()

        def wait(_headers, blueprint_pk, _blueprint_name):
            events.append(("wait", blueprint_pk))
            return True

        fake_client = mock.Mock(side_effect=post)
        with mock.patch.object(MODULE, "request_json", fake_client), mock.patch.object(
            MODULE, "wait_for_apply_result", side_effect=wait
        ), mock.patch.dict(
            MODULE.os.environ,
            {"AUTHENTIK_BASE_URL": "http://authentik-server:9000"},
            clear=True,
        ):
            MODULE.apply_sequentially({}, [("first", "First"), ("second", "Second")])

        self.assertEqual(
            events,
            [("post", "first"), ("wait", "first"), ("post", "second"), ("wait", "second")],
        )

    def test_apply_wait_accepts_a_late_success(self) -> None:
        states = iter(
            [
                {"blueprint": ("Blueprint", "error")},
                {"blueprint": ("Blueprint", "error")},
                {"blueprint": ("Blueprint", "successful")},
            ]
        )

        with mock.patch.object(MODULE, "APPLY_STATUS_ATTEMPTS", 3), mock.patch.object(
            MODULE, "get_custom_blueprints", side_effect=states
        ) as get_blueprints:
            self.assertTrue(MODULE.wait_for_apply_result({}, "blueprint", "Blueprint"))

        self.assertEqual(get_blueprints.call_count, 3)
    def test_persistent_failure_stops_before_next_blueprint(self) -> None:
        fake_client = mock.Mock(return_value=Response())
        with mock.patch.object(MODULE, "request_json", fake_client), mock.patch.object(
            MODULE, "wait_for_apply_result", return_value=False
        ), mock.patch.dict(
            MODULE.os.environ,
            {"AUTHENTIK_BASE_URL": "http://authentik-server:9000"},
            clear=True,
        ), self.assertRaisesRegex(RuntimeError, "First"):
            MODULE.apply_sequentially({}, [("first", "First"), ("second", "Second")])

        self.assertEqual(fake_client.call_count, MODULE.APPLY_ATTEMPTS)
        self.assertNotIn("second", " ".join(call.args[1] for call in fake_client.call_args_list))


if __name__ == "__main__":
    unittest.main()
