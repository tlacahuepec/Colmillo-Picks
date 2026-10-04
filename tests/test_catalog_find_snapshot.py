"""Tests for CatalogStore.find_snapshot and contract serialization."""

from services.catalog.contracts import (
    CanonicalRef,
    CatalogEvent,
    CatalogField,
    CatalogSnapshot,
    CompletenessStatus,
    Confidence,
    FreshnessStatus,
    InjurySnapshot,
    LineupSnapshot,
    PredictionMarketObservation,
    SourceObservation,
    snapshot_from_dict,
    to_catalog_dict,
)
from services.catalog.storage import CatalogStore


def _build_test_snapshot(
    snapshot_id: str = "snap-1",
    event_id: str = "nfl:event:kc-bal-2026-09-11",
    start_time: str = "2026-09-11T19:00:00Z",
) -> CatalogSnapshot:
    home = CanonicalRef(
        entity_type="team",
        canonical_id="nfl:team:kansas-city-chiefs",
        display_name="Kansas City Chiefs",
        provider_ids={"the_odds_api": "KC Chiefs"},
    )
    away = CanonicalRef(
        entity_type="team",
        canonical_id="nfl:team:baltimore-ravens",
        display_name="Baltimore Ravens",
        provider_ids={"the_odds_api": "BAL Ravens"},
    )
    event = CatalogEvent(
        event_id=event_id,
        sport="nfl",
        league="nfl",
        start_time=start_time,
        home_team=home,
        away_team=away,
    )
    obs = SourceObservation(
        observation_id="obs-1",
        provider="fixture-provider",
        observed_at="2026-09-11T12:00:00Z",
        confidence=Confidence.CONFIRMED,
    )
    fields = (
        CatalogField(
            name="total",
            value=46.5,
            observed_at="2026-09-11T12:00:00Z",
            valid_until="2026-09-11T12:15:00Z",
            freshness=FreshnessStatus.FRESH,
            confidence=Confidence.CONFIRMED,
        ),
    )
    lineup = LineupSnapshot(
        event_id=event_id,
        team_id="nfl:team:kansas-city-chiefs",
        status=Confidence.CONFIRMED,
        players=(CanonicalRef("player", "mahomes", display_name="Patrick Mahomes"),),
    )
    injury = InjurySnapshot(
        event_id=event_id,
        subject=CanonicalRef("player", "pacheco", display_name="Isiah Pacheco"),
        status="questionable",
        reason="ankle",
    )
    market = PredictionMarketObservation(
        market_id="pm-1",
        market_type="moneyline",
        selection="Kansas City Chiefs",
        displayed_price="55%",
        volume="15000",
        status="active",
        observed_at="2026-09-11T12:00:00Z",
        source_url="https://fanaticsmarkets.com/",
    )
    return CatalogSnapshot(
        snapshot_id=snapshot_id,
        event=event,
        created_at="2026-09-11T12:00:00Z",
        as_of="2026-09-11T12:00:00Z",
        completeness=CompletenessStatus.COMPLETE,
        fields=fields,
        lineups=(lineup,),
        injuries=(injury,),
        prediction_markets=(market,),
        source_observations=(obs,),
    )


def test_snapshot_serialization_roundtrip():
    original = _build_test_snapshot()
    serialized = to_catalog_dict(original)
    reconstructed = snapshot_from_dict(serialized)

    assert reconstructed.snapshot_id == original.snapshot_id
    assert reconstructed.event.event_id == original.event.event_id
    assert reconstructed.event.home_team == original.event.home_team
    assert reconstructed.event.away_team == original.event.away_team
    assert reconstructed.fields == original.fields
    assert reconstructed.lineups == original.lineups
    assert reconstructed.injuries == original.injuries
    assert reconstructed.prediction_markets == original.prediction_markets
    assert reconstructed.source_observations == original.source_observations
    assert reconstructed == original


def test_find_snapshot_exact_and_alias_matches(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    snapshot = _build_test_snapshot()
    store.save_snapshot(snapshot)

    # 1. Exact display name match
    found = store.find_snapshot(
        sport="nfl",
        home_team="Kansas City Chiefs",
        away_team="Baltimore Ravens",
        event_date="2026-09-11",
    )
    assert found is not None
    assert found.snapshot_id == "snap-1"
    assert found.event.event_id == "nfl:event:kc-bal-2026-09-11"

    # 2. Case-insensitive and punctuation-tolerant match
    found_case = store.find_snapshot(
        sport="NFL",
        home_team="kansas city chiefs",
        away_team="baltimore-ravens",
        event_date="2026-09-11",
    )
    assert found_case is not None
    assert found_case.snapshot_id == "snap-1"

    # 3. Nickname / substring match
    found_sub = store.find_snapshot(
        sport="nfl",
        home_team="Chiefs",
        away_team="Ravens",
        event_date="2026-09-11",
    )
    assert found_sub is not None
    assert found_sub.snapshot_id == "snap-1"

    # 4. Provider alias match ("KC Chiefs" in provider_ids)
    found_alias = store.find_snapshot(
        sport="nfl",
        home_team="KC Chiefs",
        away_team="BAL Ravens",
        event_date="2026-09-11",
    )
    assert found_alias is not None
    assert found_alias.snapshot_id == "snap-1"


def test_find_snapshot_returns_latest_snapshot(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    snap1 = _build_test_snapshot("snap-1")
    store.save_snapshot(snap1)

    # Second newer snapshot
    snap2 = CatalogSnapshot(
        snapshot_id="snap-2",
        event=snap1.event,
        created_at="2026-09-11T13:00:00Z",
        as_of="2026-09-11T13:00:00Z",
        completeness=CompletenessStatus.COMPLETE,
        fields=(),
    )
    store.save_snapshot(snap2)

    found = store.find_snapshot(
        sport="nfl",
        home_team="Chiefs",
        away_team="Ravens",
        event_date="2026-09-11",
    )
    assert found is not None
    assert found.snapshot_id == "snap-2"


def test_find_snapshot_non_matching_cases(tmp_path):
    store = CatalogStore(tmp_path / "catalog.db")
    snapshot = _build_test_snapshot()
    store.save_snapshot(snapshot)

    # Different date
    assert store.find_snapshot(
        sport="nfl",
        home_team="Chiefs",
        away_team="Ravens",
        event_date="2026-09-12",
    ) is None

    # Different sport
    assert store.find_snapshot(
        sport="soccer",
        home_team="Chiefs",
        away_team="Ravens",
        event_date="2026-09-11",
    ) is None

    # Different team
    assert store.find_snapshot(
        sport="nfl",
        home_team="Eagles",
        away_team="Ravens",
        event_date="2026-09-11",
    ) is None

    # Event exists without snapshot
    orphan_event = CatalogEvent(
        event_id="nfl:event:buf-mia-2026-09-11",
        sport="nfl",
        league="nfl",
        start_time="2026-09-11T20:00:00Z",
        home_team=CanonicalRef("team", "buf", display_name="Bills"),
        away_team=CanonicalRef("team", "mia", display_name="Dolphins"),
    )
    store.upsert_event(orphan_event)
    assert store.find_snapshot(
        sport="nfl",
        home_team="Bills",
        away_team="Dolphins",
        event_date="2026-09-11",
    ) is None
