from datetime import datetime, timezone
import pytest

from services.catalog.contracts import CatalogEvent, CatalogField, CatalogSnapshot, FreshnessStatus, LineupSnapshot, Confidence
from services.catalog.freshness import evaluate_field, resources_to_refresh


NOW = datetime(2026, 9, 11, 12, tzinfo=timezone.utc)
EVENT = CatalogEvent("nfl:event:1", "nfl", "nfl", "2026-09-11T18:00:00Z")


def test_field_ttls_are_independent():
    fresh_market = CatalogField("markets", {}, "2026-09-11T11:50:00Z")
    stale_form = CatalogField("form", {}, "2026-09-10T11:00:00Z")
    assert evaluate_field(fresh_market, now=NOW).status == FreshnessStatus.FRESH
    assert evaluate_field(stale_form, now=NOW).status == FreshnessStatus.STALE
    assert evaluate_field(stale_form, now=NOW).should_refresh


def test_expiry_and_unknown_timestamps_refresh_safely():
    expired = CatalogField("weather", {}, "2026-09-11T03:00:00Z")
    unknown = CatalogField("markets", {}, None)
    assert evaluate_field(expired, now=NOW).status == FreshnessStatus.EXPIRED
    assert evaluate_field(unknown, now=NOW).status == FreshnessStatus.UNKNOWN
    assert evaluate_field(unknown, now=NOW).should_refresh


def test_snapshot_returns_unique_stale_resources():
    snapshot = CatalogSnapshot(
        "s1", EVENT, "2026-09-11T11:00:00Z", "2026-09-11T11:00:00Z",
        fields=(CatalogField("markets", {}, "2026-09-11T11:00:00Z"),
                CatalogField("form.home", {}, "2026-09-10T11:00:00Z")),
        lineups=(LineupSnapshot("nfl:event:1", "nfl:team:home", Confidence.CONFIRMED,
                                observed_at="2026-09-11T09:00:00Z"),),
    )
    assert resources_to_refresh(snapshot, now=NOW) == ("form.home", "lineups", "markets")


@pytest.mark.parametrize(
    ("resource", "minutes_fresh", "minutes_stale", "minutes_expired"),
    [
        ("markets", 10, 20, 35),
        ("odds", 10, 20, 35),
        ("lineups", 90, 180, 300),
        ("injuries", 90, 180, 300),
        ("weather", 120, 240, 400),
        ("form", 720, 1800, 3000),
        ("stable", 720, 1800, 3000),
    ],
)
def test_all_field_ttls_matrix(resource, minutes_fresh, minutes_stale, minutes_expired):
    from datetime import timedelta
    from services.catalog.freshness import DEFAULT_FRESHNESS_POLICY

    t_fresh = (NOW - timedelta(minutes=minutes_fresh)).isoformat()
    t_stale = (NOW - timedelta(minutes=minutes_stale)).isoformat()
    t_expired = (NOW - timedelta(minutes=minutes_expired)).isoformat()

    fresh_dec = evaluate_field(CatalogField(resource, {}, t_fresh), now=NOW, policy=DEFAULT_FRESHNESS_POLICY)
    assert fresh_dec.status == FreshnessStatus.FRESH
    assert not fresh_dec.should_refresh

    stale_dec = evaluate_field(CatalogField(resource, {}, t_stale), now=NOW, policy=DEFAULT_FRESHNESS_POLICY)
    assert stale_dec.status == FreshnessStatus.STALE
    assert stale_dec.should_refresh

    expired_dec = evaluate_field(CatalogField(resource, {}, t_expired), now=NOW, policy=DEFAULT_FRESHNESS_POLICY)
    assert expired_dec.status == FreshnessStatus.EXPIRED
    assert expired_dec.should_refresh


def test_hierarchical_dotted_field_ttl_resolution():
    from services.catalog.freshness import DEFAULT_FRESHNESS_POLICY

    assert DEFAULT_FRESHNESS_POLICY.ttl_for("markets.spreads") == DEFAULT_FRESHNESS_POLICY.field_ttls["markets"]
    assert DEFAULT_FRESHNESS_POLICY.ttl_for("odds.player_props") == DEFAULT_FRESHNESS_POLICY.field_ttls["odds"]
    assert DEFAULT_FRESHNESS_POLICY.ttl_for("form.away") == DEFAULT_FRESHNESS_POLICY.field_ttls["form"]
    assert DEFAULT_FRESHNESS_POLICY.ttl_for("completely_unknown_field") == DEFAULT_FRESHNESS_POLICY.default_ttl


def test_explicit_valid_until_overrides_ttl():
    # Observed 1 hour ago, but valid_until set to 10 minutes from NOW -> should be FRESH
    field_fresh = CatalogField(
        "odds",
        {},
        observed_at="2026-09-11T11:00:00Z",
        valid_until="2026-09-11T12:10:00Z",
    )
    dec = evaluate_field(field_fresh, now=NOW)
    assert dec.status == FreshnessStatus.FRESH
    assert not dec.should_refresh

    # valid_until expired 5 minutes ago (within 15m TTL window) -> STALE
    field_stale = CatalogField(
        "odds",
        {},
        observed_at="2026-09-11T11:00:00Z",
        valid_until="2026-09-11T11:55:00Z",
    )
    dec = evaluate_field(field_stale, now=NOW)
    assert dec.status == FreshnessStatus.STALE
    assert dec.should_refresh

    # valid_until expired 30 minutes ago (beyond 15m TTL window) -> EXPIRED
    field_expired = CatalogField(
        "odds",
        {},
        observed_at="2026-09-11T11:00:00Z",
        valid_until="2026-09-11T11:30:00Z",
    )
    dec = evaluate_field(field_expired, now=NOW)
    assert dec.status == FreshnessStatus.EXPIRED
    assert dec.should_refresh


def test_clock_skew_and_malformed_timestamps():
    # Future timestamp (clock skew where now < observed_at)
    future_field = CatalogField("odds", {}, "2026-09-11T12:30:00Z")
    dec = evaluate_field(future_field, now=NOW)
    assert dec.status == FreshnessStatus.UNKNOWN
    assert dec.should_refresh

    # Malformed timestamp string
    bad_field = CatalogField("odds", {}, "not-a-date")
    dec = evaluate_field(bad_field, now=NOW)
    assert dec.status == FreshnessStatus.UNKNOWN
    assert dec.should_refresh

    # Malformed valid_until
    bad_valid = CatalogField("odds", {}, "2026-09-11T11:50:00Z", valid_until="gibberish")
    dec = evaluate_field(bad_valid, now=NOW)
    assert dec.status == FreshnessStatus.UNKNOWN
    assert dec.should_refresh


def test_selective_refresh_refreshes_only_stale_resources():
    from services.catalog.contracts import InjurySnapshot, CanonicalRef
    from services.catalog.freshness import missing_resources

    # Snapshot with:
    # - Stale odds (30m old > 15m TTL)
    # - Fresh weather (1h old < 3h TTL)
    # - Fresh lineups (1h old < 2h TTL)
    # - Fresh injuries (1h old < 2h TTL)
    snapshot = CatalogSnapshot(
        "s-selective",
        EVENT,
        "2026-09-11T11:30:00Z",
        "2026-09-11T11:30:00Z",
        fields=(
            CatalogField("odds", {"moneyline": -110}, "2026-09-11T11:30:00Z"),
            CatalogField("weather", {"temp": 72}, "2026-09-11T11:00:00Z"),
        ),
        lineups=(
            LineupSnapshot(
                "nfl:event:1",
                "nfl:team:home",
                Confidence.CONFIRMED,
                observed_at="2026-09-11T11:00:00Z",
            ),
        ),
        injuries=(
            InjurySnapshot(
                "nfl:event:1",
                CanonicalRef("player", "mahomes"),
                status="active",
                observed_at="2026-09-11T11:00:00Z",
            ),
        ),
    )

    # Only "odds" is stale; weather, lineups, and injuries must NOT be marked for refresh
    stale_resources = resources_to_refresh(snapshot, now=NOW)
    assert stale_resources == ("odds",)

    # missing_resources check
    missing = missing_resources(snapshot, ["odds", "weather", "lineups", "injuries", "fanatics_markets"])
    assert missing == ("fanatics_markets",)

