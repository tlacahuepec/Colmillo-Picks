import httpx

from services.ui.api_client import APIClientConfig, PicksAPIClient


def test_catalog_client_lists_events_and_snapshots():
    def handler(request):
        if request.url.path == "/catalog/events":
            return httpx.Response(200, json={"items": [], "limit": 10, "offset": 0})
        return httpx.Response(200, json={"snapshot_id": "s1"})

    client = PicksAPIClient(APIClientConfig("http://test", ""), transport=httpx.MockTransport(handler))
    assert client.list_catalog_events(limit=10)["items"] == []
    assert client.get_catalog_snapshot("nfl:event:1")["snapshot_id"] == "s1"
