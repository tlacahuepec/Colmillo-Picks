"""Tests for the COLMILLO_USE_LANGGRAPH feature toggle (S01, #253)."""

from __future__ import annotations

from llm.provider_adapter import _read_langgraph_toggle, build_enrich_with_llm


class TestReadLanggraphToggle:
    """Unit tests for the toggle-reading helper."""

    def test_returns_true_when_env_is_true(self):
        env = {"COLMILLO_USE_LANGGRAPH": "true"}
        assert _read_langgraph_toggle(env.get) is True

    def test_returns_true_when_env_is_TRUE_uppercase(self):
        env = {"COLMILLO_USE_LANGGRAPH": "TRUE"}
        assert _read_langgraph_toggle(env.get) is True

    def test_returns_true_when_env_is_1(self):
        env = {"COLMILLO_USE_LANGGRAPH": "1"}
        assert _read_langgraph_toggle(env.get) is True

    def test_returns_false_when_env_is_false(self):
        env = {"COLMILLO_USE_LANGGRAPH": "false"}
        assert _read_langgraph_toggle(env.get) is False

    def test_returns_false_when_env_is_absent(self):
        env: dict[str, str] = {}
        assert _read_langgraph_toggle(env.get) is False

    def test_returns_false_when_env_is_empty_string(self):
        env = {"COLMILLO_USE_LANGGRAPH": ""}
        assert _read_langgraph_toggle(env.get) is False


class TestBuildEnrichToggleOff:
    """Verify that toggle-off preserves existing behavior."""

    def test_toggle_off_returns_callable(self):
        env = {"COLMILLO_USE_LANGGRAPH": "false"}

        fn = build_enrich_with_llm(
            use_llm=False,
            llm_provider=None,
            llm_model=None,
            use_langgraph=False,
            getenv=env.get,
        )

        assert callable(fn)

    def test_toggle_off_use_langgraph_true_returns_callable(self):
        env = {"COLMILLO_USE_LANGGRAPH": "false"}

        fn = build_enrich_with_llm(
            use_llm=False,
            llm_provider=None,
            llm_model=None,
            use_langgraph=True,
            getenv=env.get,
        )

        assert callable(fn)

    def test_toggle_absent_defaults_to_langchain_enricher(self):
        env: dict[str, str] = {}

        fn = build_enrich_with_llm(
            use_llm=False,
            llm_provider=None,
            llm_model=None,
            getenv=env.get,
        )

        assert callable(fn)


class TestLanggraphImport:
    """Verify langgraph package is importable after dependency addition."""

    def test_langgraph_import_succeeds(self):
        import langgraph  # noqa: F401

    def test_langchain_core_import_succeeds(self):
        import langchain_core  # noqa: F401
