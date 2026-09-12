import pytest

from services.catalog.archive import ArchivePolicy, prepare_archive, redact_archive
from services.catalog.storage import CatalogStore


def test_archive_redacts_secrets_and_signed_urls():
    archive_id, encoded = prepare_archive({"api_key": "secret", "url": "https://x.test?a=1&token=abc", "nested": {"cookie": "x"}})
    assert len(archive_id) == 64
    assert "secret" not in encoded and "token=abc" not in encoded
    assert redact_archive({"authorization": "Bearer x"})["authorization"] == "[REDACTED]"


def test_archive_enforces_size_and_retention(tmp_path):
    with pytest.raises(ValueError):
        prepare_archive({"data": "x" * 20}, policy=ArchivePolicy(max_bytes=10))
    store = CatalogStore(tmp_path / "catalog.db")
    archive_id = store.save_raw_archive(provider="fixture", payload={"ok": True}, created_at="2026-01-01T00:00:00Z", policy=ArchivePolicy(retention_days=1))
    item = store.get_raw_archive(archive_id)
    assert item["warning"]
    assert store.purge_expired_archives(now="2026-01-03T00:00:00Z") == 1
    assert store.get_raw_archive(archive_id) is None
