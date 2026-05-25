"""Tests for availability badge status mapping logic."""

from __future__ import annotations

from services.ui.availability_badges import classify_badge, BadgeStatus


class TestClassifyBadge:
    def test_available_matching_line(self):
        badge = classify_badge(
            platform_status="available",
            platform_line=1.5,
            recommended_line=1.5,
        )
        assert badge == BadgeStatus.AVAILABLE

    def test_available_different_line(self):
        badge = classify_badge(
            platform_status="available",
            platform_line=2.5,
            recommended_line=1.5,
        )
        assert badge == BadgeStatus.LINE_DIFFERS

    def test_unavailable(self):
        badge = classify_badge(
            platform_status="unavailable",
            platform_line=None,
            recommended_line=1.5,
        )
        assert badge == BadgeStatus.UNAVAILABLE

    def test_unknown(self):
        badge = classify_badge(
            platform_status="unknown",
            platform_line=None,
            recommended_line=1.5,
        )
        assert badge == BadgeStatus.UNKNOWN

    def test_available_no_platform_line_treated_as_available(self):
        badge = classify_badge(
            platform_status="available",
            platform_line=None,
            recommended_line=1.5,
        )
        assert badge == BadgeStatus.AVAILABLE

    def test_available_same_line_float_tolerance(self):
        badge = classify_badge(
            platform_status="available",
            platform_line=1.50000001,
            recommended_line=1.5,
        )
        assert badge == BadgeStatus.AVAILABLE


class TestBadgeStatusLabels:
    def test_available_label(self):
        assert BadgeStatus.AVAILABLE.label == "Available"

    def test_line_differs_label(self):
        assert BadgeStatus.LINE_DIFFERS.label == "Line differs"

    def test_unavailable_label(self):
        assert BadgeStatus.UNAVAILABLE.label == "Not available"

    def test_unknown_label(self):
        assert BadgeStatus.UNKNOWN.label == "Could not check"

    def test_available_icon(self):
        assert BadgeStatus.AVAILABLE.icon == "\u2705"

    def test_line_differs_icon(self):
        assert BadgeStatus.LINE_DIFFERS.icon == "\u26a0\ufe0f"

    def test_unavailable_icon(self):
        assert BadgeStatus.UNAVAILABLE.icon == "\u274c"

    def test_unknown_icon(self):
        assert BadgeStatus.UNKNOWN.icon == "\u2753"
