"""Keep the CVE-2026-114603 parser fix when updating telemetry dependencies."""
import subprocess
import sys

from opentelemetry.trace import TraceState


def test_long_malformed_tracestate_does_not_stall_parser():
    """Bound parsing time for the malformed header that triggered the CVE."""
    # Bound the vulnerable parser's runtime in a child process, never a server.
    result = subprocess.run(
        [sys.executable, "-c", """
import logging
from opentelemetry.trace import TraceState
logging.disable(logging.CRITICAL)
assert list(TraceState.from_header(["vendor=value" + " " * 1_000_000 + "!"]).items()) == []
"""],
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr


def test_valid_tracestate_is_preserved():
    """Preserve valid tracing entries after the dependency upgrade."""
    assert list(TraceState.from_header(["vendor=value,other=second"]).items()) == [
        ("vendor", "value"), ("other", "second"),
    ]
