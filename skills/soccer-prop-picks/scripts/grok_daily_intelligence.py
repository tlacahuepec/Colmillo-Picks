"""Backward-compatibility shim — use daily_intelligence module directly."""

from __future__ import annotations

from daily_intelligence import DailyIntelligenceClient as GrokDailyIntelligenceClient
from daily_intelligence import DailyIntelligenceError as GrokDailyIntelligenceError

__all__ = ["GrokDailyIntelligenceClient", "GrokDailyIntelligenceError"]
