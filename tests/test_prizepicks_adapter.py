from __future__ import annotations

import httpx

from availability.prizepicks import PrizePicksAdapter


def _payload() -> dict[str, object]:
    return {
        "data": [
            {
                "type": "projection",
                "attributes": {"stat_type": "Passes Attempted", "line_score": 52.5},
                "relationships": {"new_player": {"data": {"id": "player-1", "type": "new_player"}}},
            }
        ],
        "included": [{"type": "new_player", "id": "player-1", "attributes": {"name": "Mohamed Salah"}}],
    }


def test_prizepicks_adapter_matches_fuzzy_player_name_and_line() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = PrizePicksAdapter(client=client, cache_ttl_seconds=300)

    result = adapter.check_availability(player="M Salah", market="Passes Attempted", line=52.5)

    assert result.available is True
    assert result.platform == "prizepicks"


def test_prizepicks_adapter_uses_cache_within_ttl() -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=_payload())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = PrizePicksAdapter(client=client, cache_ttl_seconds=300)

    adapter.check_availability(player="Mohamed Salah", market="Passes Attempted", line=52.5)
    adapter.check_availability(player="Mohamed Salah", market="Passes Attempted", line=52.5)

    assert calls["count"] == 1


def test_prizepicks_adapter_gracefully_degrades_when_platform_down() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = PrizePicksAdapter(client=client)

    payload = adapter.check_picks([{"player_id": "liv-11", "player_name": "Mohamed Salah", "market": "shots", "line": "3.5"}])

    entry = payload["picks"]["liv-11:shots"]
    assert payload["fallback_mode"] is True
    assert payload["fallback_reason"] == "platform_down"
    assert entry["prizepicks"] == "unknown"
