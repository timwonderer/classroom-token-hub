"""FEAT-CLASS-004 effective_at parsing: an offset-less string names no instant (SPEC-TIME-001 §VI)."""

from datetime import datetime, timezone

from app.feats.class_configuration.feat_class_004_feature_enablement import (
    _parse_effective_at_timestamp,
)


def test_effective_at_with_offset_parses_aware():
    assert _parse_effective_at_timestamp("2026-10-23T08:00:00+00:00") == datetime(
        2026, 10, 23, 8, tzinfo=timezone.utc
    )


def test_effective_at_without_offset_is_rejected_not_assumed_utc():
    assert _parse_effective_at_timestamp("2026-10-23T08:00:00") is None
    assert _parse_effective_at_timestamp("not a date") is None
