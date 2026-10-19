#!/usr/bin/env python3
"""Export a production Langfuse ingestion round trip for Prometheus alerting."""

import os
from pathlib import Path
import sys
import tempfile
import time


METRIC_DIRECTORY = Path('prometheus/textfile')
METRIC_FILE = METRIC_DIRECTORY / 'langfuse_ingestion.prom'


def write_metrics(success, timestamp=None, directory=METRIC_DIRECTORY):
    """Atomically publish only a result bit and completion time, never event data."""
    if directory.is_symlink() or not directory.is_dir():
        raise RuntimeError('Langfuse monitor metric directory is missing or unsafe')
    target = directory / METRIC_FILE.name
    payload = (
        '# HELP llm_stack_langfuse_ingestion_probe_success End-to-end ingestion result.\n'
        '# TYPE llm_stack_langfuse_ingestion_probe_success gauge\n'
        f'llm_stack_langfuse_ingestion_probe_success {int(success)}\n'
        '# HELP llm_stack_langfuse_ingestion_probe_timestamp_seconds Last completed probe time.\n'
        '# TYPE llm_stack_langfuse_ingestion_probe_timestamp_seconds gauge\n'
        f'llm_stack_langfuse_ingestion_probe_timestamp_seconds {int(time.time() if timestamp is None else timestamp)}\n'
    )
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                         prefix='.langfuse-ingestion-', delete=False) as output:
            temp_path = Path(output.name)
            os.fchmod(output.fileno(), 0o644)
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_path, target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def run_probe():
    from smoke_test import test_langfuse_ingestion

    return test_langfuse_ingestion('production')


def run_monitor(probe=run_probe, publish=write_metrics, timestamp=None):
    if (os.environ.get('SMOKE_ENVIRONMENT') != 'production'
            or os.environ.get('SMOKE_PROD_LANGFUSE_INGESTION') != '1'
            or os.environ.get('SMOKE_UAT_IDENTITY_FILE')):
        raise RuntimeError('Production ingestion monitor requires explicit production attestation')

    try:
        probe()
        success = True
    except Exception:
        success = False

    publish(success, timestamp)
    return success


def main():
    try:
        success = run_monitor()
    except Exception as exc:
        print(f'Langfuse ingestion monitor publication failed: {type(exc).__name__}', file=sys.stderr)
        return 2
    print('Langfuse ingestion probe OK' if success else 'Langfuse ingestion probe FAILED',
          file=sys.stdout if success else sys.stderr)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
