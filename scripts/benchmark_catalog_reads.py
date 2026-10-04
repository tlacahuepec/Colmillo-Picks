"""Benchmark catalog-first read latency vs live pipeline generation.

Measures local SQLite cache lookup latency across repeated reads, calculates
p50/p95/p99 percentiles, and compares against typical live LLM discovery latency.
Run from repository root:
    python scripts/benchmark_catalog_reads.py
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import statistics
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.catalog.contracts import (  # noqa: E402
    CanonicalRef,
    CatalogEvent,
    CatalogField,
    CatalogSnapshot,
    CompletenessStatus,
    Confidence,
    FreshnessStatus,
    LineupSnapshot,
    PredictionMarketObservation,
    SourceObservation,
)
from services.catalog.freshness import DEFAULT_FRESHNESS_POLICY  # noqa: E402
from services.catalog.read_service import CatalogFirstReader  # noqa: E402
from services.catalog.storage import CatalogStore  # noqa: E402


def _seed_catalog(store: CatalogStore, count: int = 50) -> list[tuple[str, str, str, str]]:
    """Seed the database with test events and snapshots across multiple sports."""
    seeded_queries: list[tuple[str, str, str, str]] = []
    sports = ["nfl", "soccer", "basketball", "baseball"]
    now_iso = datetime.now(timezone.utc).isoformat()

    for i in range(count):
        sport = sports[i % len(sports)]
        home_slug = f"team-home-{i}"
        away_slug = f"team-away-{i}"
        home_name = f"Home Team {i}"
        away_name = f"Away Team {i}"
        event_date = "2026-10-05"
        event_id = f"{sport}:event:{i}"

        event = CatalogEvent(
            event_id=event_id,
            sport=sport,
            league=f"{sport}_league",
            start_time=f"{event_date}T19:00:00Z",
            home_team=CanonicalRef("team", f"{sport}:team:{home_slug}", display_name=home_name),
            away_team=CanonicalRef("team", f"{sport}:team:{away_slug}", display_name=away_name),
        )

        snapshot = CatalogSnapshot(
            snapshot_id=f"snap-{i}",
            event=event,
            created_at=now_iso,
            as_of=now_iso,
            completeness=CompletenessStatus.COMPLETE,
            fields=(
                CatalogField("odds", {"moneyline": -115}, now_iso, freshness=FreshnessStatus.FRESH),
                CatalogField("markets", {"spread": -2.5}, now_iso, freshness=FreshnessStatus.FRESH),
                CatalogField("weather", {"temperature": 70}, now_iso, freshness=FreshnessStatus.FRESH),
            ),
            lineups=(
                LineupSnapshot(event_id, f"{sport}:team:{home_slug}", Confidence.CONFIRMED, observed_at=now_iso),
            ),
            prediction_markets=(
                PredictionMarketObservation(
                    market_id=f"pm-{i}",
                    market_type="moneyline",
                    selection=home_name,
                    displayed_price="54%",
                    volume="25000",
                    status="active",
                    observed_at=now_iso,
                    source_url="https://fanaticsmarkets.com/",
                ),
            ),
            source_observations=(
                SourceObservation(f"obs-{i}", "fixture-provider", now_iso, confidence=Confidence.CONFIRMED),
            ),
        )
        store.save_snapshot(snapshot)
        seeded_queries.append((sport, home_name, away_name, event_date))

    return seeded_queries


def run_benchmark(iterations: int = 100, live_baseline_ms: float = 6500.0) -> int:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "catalog_bench.db"
        store = CatalogStore(db_path)
        queries = _seed_catalog(store, count=50)

        reader = CatalogFirstReader(
            lookup=lambda s, h, a, d: store.find_snapshot(sport=s, home_team=h, away_team=a, event_date=d),
            policy=DEFAULT_FRESHNESS_POLICY,
        )

        # Warm-up (10 reads)
        now = datetime.now(timezone.utc)
        for i in range(10):
            q = queries[i % len(queries)]
            reader.read(sport=q[0], home_team=q[1], away_team=q[2], event_date=q[3], now=now)

        # Timed cache hits
        hit_latencies_ms: list[float] = []
        for i in range(iterations):
            q = queries[i % len(queries)]
            t0 = time.perf_counter()
            res = reader.read(sport=q[0], home_team=q[1], away_team=q[2], event_date=q[3], now=now)
            t1 = time.perf_counter()
            hit_latencies_ms.append((t1 - t0) * 1000.0)
            assert res.source in ("catalog", "catalog_stale"), f"Expected catalog hit, got {res.source}"

        # Timed cache misses
        miss_latencies_ms: list[float] = []
        for i in range(min(50, iterations)):
            t0 = time.perf_counter()
            res = reader.read(
                sport="nfl",
                home_team=f"NonExistentHome{i}",
                away_team=f"NonExistentAway{i}",
                event_date="2026-10-05",
                now=now,
            )
            t1 = time.perf_counter()
            miss_latencies_ms.append((t1 - t0) * 1000.0)
            assert res.source == "live", f"Expected live fallback on miss, got {res.source}"

        hit_sorted = sorted(hit_latencies_ms)
        p50 = statistics.median(hit_sorted)
        p95 = hit_sorted[max(0, int(len(hit_sorted) * 0.95) - 1)]
        p99 = hit_sorted[max(0, int(len(hit_sorted) * 0.99) - 1)]
        mean = statistics.mean(hit_sorted)
        min_lat = min(hit_sorted)
        max_lat = max(hit_sorted)

        miss_p50 = statistics.median(miss_latencies_ms)

        speedup = live_baseline_ms / mean if mean > 0 else 0

        print("=" * 68)
        print(" CATALOG-FIRST READ PERFORMANCE BENCHMARK ")
        print("=" * 68)
        print(f"Iterations:          {iterations} reads across 50 seeded catalog events")
        print("Database:            SQLite (WAL mode, index-backed)")
        print("-" * 68)
        print("CACHE HIT LATENCY (ms):")
        print(f"  Min:               {min_lat:.3f} ms")
        print(f"  Mean:              {mean:.3f} ms")
        print(f"  Median (p50):      {p50:.3f} ms")
        print(f"  p95:               {p95:.3f} ms")
        print(f"  p99:               {p99:.3f} ms")
        print(f"  Max:               {max_lat:.3f} ms")
        print("-" * 68)
        print("CACHE MISS LATENCY (ms):")
        print(f"  Median (p50):      {miss_p50:.3f} ms")
        print("-" * 68)
        print("COMPARISON VS LIVE PIPELINE GENERATION:")
        print(f"  Catalog Cache Hit: {p50:.3f} ms")
        print(f"  Live LLM Baseline: {live_baseline_ms:.1f} ms")
        print(f"  Latency Speedup:   {speedup:.1f}x faster")
        print("  Token Savings:     100% on cache hits (0 LLM tokens consumed)")
        print("  Network Calls:     0 external provider calls on cache hits")
        print("=" * 68)

        # Target verification: p95 must be < 10.0 ms
        if p95 < 10.0:
            print(f"[PASS] p95 latency ({p95:.3f} ms) is well within target (< 10.0 ms)")
            return 0
        else:
            print(f"[WARN] p95 latency ({p95:.3f} ms) exceeded 10.0 ms target")
            return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark catalog-first read latency.")
    parser.add_argument("--iterations", type=int, default=100, help="Number of read iterations (default: 100)")
    parser.add_argument("--baseline-ms", type=float, default=6500.0, help="Live pipeline baseline in ms (default: 6500)")
    args = parser.parse_args()
    sys.exit(run_benchmark(iterations=args.iterations, live_baseline_ms=args.baseline_ms))
