"""Unit tests for the production Langfuse ingestion monitor."""

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'langfuse_ingestion_monitor.py'
SPEC = importlib.util.spec_from_file_location('langfuse_ingestion_monitor', SCRIPT)
MONITOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MONITOR)


class LangfuseIngestionMonitorTests(unittest.TestCase):
    def setUp(self):
        self.environment = mock.patch.dict(os.environ, {
            'SMOKE_ENVIRONMENT': 'production',
            'SMOKE_PROD_LANGFUSE_INGESTION': '1',
            'SMOKE_UAT_IDENTITY_FILE': '',
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_success_publishes_one_without_event_data(self):
        published = []
        success = MONITOR.run_monitor(lambda: 'HTTP 207',
                                      lambda result, when: published.append((result, when)), 123)
        self.assertTrue(success)
        self.assertEqual(published, [(True, 123)])

    def test_probe_failure_publishes_zero_without_exception_text(self):
        published = []

        def fail():
            raise RuntimeError('secret-token and private trace body')

        success = MONITOR.run_monitor(fail,
                                      lambda result, when: published.append((result, when)), 123)
        self.assertFalse(success)
        self.assertEqual(published, [(False, 123)])

    def test_wrong_attestation_fails_before_probe_or_publish(self):
        with mock.patch.dict(os.environ, {'SMOKE_ENVIRONMENT': 'uat'}):
            probe = mock.Mock()
            publish = mock.Mock()
            with self.assertRaisesRegex(RuntimeError, 'production attestation'):
                MONITOR.run_monitor(probe, publish, 123)
            probe.assert_not_called()
            publish.assert_not_called()

    def test_publication_failure_is_not_silenced(self):
        def fail_publication(_result, _when):
            raise PermissionError('metric directory unavailable')

        with self.assertRaises(PermissionError):
            MONITOR.run_monitor(lambda: None, fail_publication, 123)

    def test_metric_is_atomic_and_contains_no_dynamic_text(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            MONITOR.write_metrics(False, 123, directory)
            metric = (directory / 'langfuse_ingestion.prom').read_text()
            self.assertIn('llm_stack_langfuse_ingestion_probe_success 0\n', metric)
            self.assertIn('llm_stack_langfuse_ingestion_probe_timestamp_seconds 123\n', metric)
            self.assertEqual([path.name for path in directory.iterdir()], ['langfuse_ingestion.prom'])
            MONITOR.write_metrics(True, 124, directory)
            self.assertIn('llm_stack_langfuse_ingestion_probe_success 1\n',
                          (directory / 'langfuse_ingestion.prom').read_text())

    def test_symlinked_metric_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'link').symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'unsafe'):
                MONITOR.write_metrics(False, 123, root / 'link')


if __name__ == '__main__':
    unittest.main()
