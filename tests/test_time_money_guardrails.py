"""
Guardrail tests to prevent regressions in datetime and money handling.
"""

from pathlib import Path
import re


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


def _iter_python_files():
    for path in APP_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def test_no_direct_datetime_now_calls_outside_time_util():
    offenders = []
    for path in _iter_python_files():
        if path.as_posix().endswith("app/utils/time.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bdatetime\.utcnow\(", text) or re.search(r"\bdatetime\.now\(", text):
            offenders.append(path.as_posix())

    assert not offenders, f"Use utc_now() helper instead of direct datetime.now/utcnow: {offenders}"


def test_no_ad_hoc_replace_tzinfo_utc_outside_time_util():
    offenders = []
    for path in _iter_python_files():
        if path.as_posix().endswith("app/utils/time.py"):
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"replace\(tzinfo=timezone\.utc\)", text):
            offenders.append(path.as_posix())

    assert not offenders, f"Use ensure_utc() instead of ad-hoc replace(tzinfo=timezone.utc): {offenders}"


def test_no_generic_float_zero_fallbacks_in_routes():
    """
    Prevent reintroducing ambiguous float defaults in route logic.
    """
    allowed_line_patterns = (
        "hold_seconds = 0.0",
        "gate_hold_seconds = 0.0",
    )

    offenders = []
    routes_root = APP_ROOT / "routes"
    for path in routes_root.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            if not re.search(r"(?<![\d])0\.0(?!\d)", line):
                continue
            if any(token in line for token in allowed_line_patterns):
                continue
            offenders.append(f"{path.as_posix()}:{idx}")

    assert not offenders, f"Use Decimal-safe defaults or explicit non-money justification: {offenders}"
