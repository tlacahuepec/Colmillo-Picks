from copy import deepcopy
from types import SimpleNamespace

import pytest

from nfl_collection import NflCollector
from tests.test_nfl import context, offer


class Client:
    def __init__(self, *, citations=True, offer_failure=False):
        self.calls = 0
        self.citations = citations
        self.offer_failure = offer_failure
        self.last_sources = []

    def generate_structured(self, **kwargs):
        self.calls += 1
        assert "schema" in kwargs
        if self.calls == 1:
            data = context()
            urls = ["https://www.nfl.com/schedules/", "https://www.nfl.com/stats/"]
        elif self.calls == 2:
            if self.offer_failure:
                raise ValueError("provider down")
            data, urls = {"offers": []}, []
        else:
            if self.offer_failure:
                raise ValueError("provider down")
            data = {
                "offers": [
                    offer(),
                    offer(source_url="https://invented.example/odds"),
                    {"bad": True},
                ]
            }
            urls = [offer()["source_url"]]
        self.last_sources = (
            [SimpleNamespace(url=url) for url in urls] if self.citations else []
        )
        return deepcopy(data)


def test_collects_only_cited_offers_and_normalizes_teams():
    data = NflCollector(Client())(
        home_team="KC", away_team="BUF", match_date="2026-09-10"
    )
    assert len(data["offers"]) == 1
    assert data["game"]["home_team"] == "Kansas City Chiefs"
    assert len(data["exclusions"]) == 2


def test_model_claimed_sources_without_search_citations_are_not_evidence():
    client = Client(citations=False)
    data = NflCollector(client)(
        home_team="KC", away_team="BUF", match_date="2026-09-10"
    )
    assert data["game"] is None and data["offers"] == []
    assert client.calls == 1


def test_offer_failure_preserves_collected_context():
    data = NflCollector(Client(offer_failure=True))(
        home_team="KC", away_team="BUF", match_date="2026-09-10"
    )
    assert data["game"] and data["players"]
    assert data["offers"] == []
    assert data["provider_statuses"]["offers"] == "unavailable"


@pytest.mark.parametrize("home,date", [("MIA", "2026-09-10"), ("KC", "2026-09-11")])
def test_rejects_wrong_fixture(home, date):
    data = NflCollector(Client())(home_team=home, away_team="BUF", match_date=date)
    assert data["game"] is None and not data["offers"]


def test_provider_redirects_are_matched_to_their_destination(monkeypatch):
    from nfl_collection import _source_urls, _grounded_sources

    monkeypatch.setattr(
        "nfl_collection._resolve_citation_url",
        lambda url: "https://www.nfl.com/schedules/",
    )
    client = SimpleNamespace(
        last_sources=[
            SimpleNamespace(
                url="https://vertexaisearch.cloud.google.com/grounding-api-redirect/test"
            )
        ]
    )
    assert _grounded_sources(
        ["https://www.nfl.com/schedules/"], _source_urls(client)
    ) == ["https://www.nfl.com/schedules/"]


def test_search_query_fallback_is_not_a_source(monkeypatch):
    from nfl_collection import _source_urls

    monkeypatch.setattr(
        "nfl_collection._resolve_citation_url",
        lambda url: "https://www.google.com/search?q=NFL",
    )
    client = SimpleNamespace(
        last_sources=[
            SimpleNamespace(
                url="https://vertexaisearch.cloud.google.com/grounding-api-redirect/test"
            )
        ]
    )
    assert _source_urls(client) == set()


def test_malformed_player_does_not_discard_game_or_other_players():
    class PartialClient(Client):
        def generate_structured(self, **kwargs):
            data = super().generate_structured(**kwargs)
            if self.calls == 1:
                data["players"].append({"player_name": "Broken"})
            return data

    data = NflCollector(PartialClient())(
        home_team="KC", away_team="BUF", match_date="2026-09-10"
    )
    assert data["game"] and len(data["players"]) == 1 and data["offers"]


def test_game_offer_failure_does_not_block_player_offers():
    class PartialClient(Client):
        def generate_structured(self, **kwargs):
            if self.calls == 1:
                self.calls += 1
                raise ValueError("game lines unavailable")
            return super().generate_structured(**kwargs)

    data = NflCollector(PartialClient())(
        home_team="KC", away_team="BUF", match_date="2026-09-10"
    )
    assert len(data["offers"]) == 1
    assert data["provider_statuses"]["game_offers"] == "unavailable"
    assert data["provider_statuses"]["player_offers"] == "ok"
    assert data["provider_statuses"]["offers"] == "ok"
    assert data["provider_errors"]["game_offers"]["type"] == "ValueError"


def test_exact_research_citations_do_not_need_redirect_requests(monkeypatch):
    from nfl_collection import _source_urls

    url = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/source"
    client = SimpleNamespace(
        last_sources=[SimpleNamespace(url=url)],
        last_research_evidence={"text": "Cited research"},
    )
    monkeypatch.setattr(
        "nfl_collection._resolve_citation_url",
        lambda url: pytest.fail("No redirect lookup needed"),
    )
    assert _source_urls(client, referenced_urls=[url]) == {url}
