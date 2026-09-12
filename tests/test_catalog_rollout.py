from services.catalog.rollout import CatalogReadMode, resolve_read_mode, should_use_catalog


def test_rollout_defaults_to_shadow_and_rejects_unknown_values():
    assert resolve_read_mode(None) == CatalogReadMode.SHADOW
    assert resolve_read_mode("bad") == CatalogReadMode.SHADOW
    assert resolve_read_mode("catalog_first") == CatalogReadMode.CATALOG_FIRST
    assert should_use_catalog(CatalogReadMode.CATALOG_FIRST, snapshot_available=True)
    assert not should_use_catalog(CatalogReadMode.SHADOW, snapshot_available=True)
