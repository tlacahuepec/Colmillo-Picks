"""Availability badge classification logic.

Pure functions with no Streamlit dependency — tested independently.
"""

from __future__ import annotations

from enum import Enum


class BadgeStatus(Enum):
    AVAILABLE = ("Available", "\u2705")
    LINE_DIFFERS = ("Line differs", "\u26a0\ufe0f")
    UNAVAILABLE = ("Not available", "\u274c")
    UNKNOWN = ("Could not check", "\u2753")

    def __init__(self, label: str, icon: str) -> None:
        self._label = label
        self._icon = icon

    @property
    def label(self) -> str:
        return self._label

    @property
    def icon(self) -> str:
        return self._icon


def classify_badge(
    *,
    platform_status: str,
    platform_line: float | None,
    recommended_line: float,
) -> BadgeStatus:
    if platform_status == "unavailable":
        return BadgeStatus.UNAVAILABLE
    if platform_status == "unknown":
        return BadgeStatus.UNKNOWN
    if platform_status == "available":
        if platform_line is not None and abs(platform_line - recommended_line) > 0.01:
            return BadgeStatus.LINE_DIFFERS
        return BadgeStatus.AVAILABLE
    return BadgeStatus.UNKNOWN
