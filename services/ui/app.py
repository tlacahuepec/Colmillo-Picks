"""Streamlit UI for Colmillo-Picks.

Two pages live in this single app file (selectable from the sidebar):

* **Generate** – Form to call ``POST /picks`` and render the markdown report.
* **History** – Lists past runs from ``GET /picks`` and replays a stored
  report when a row is selected (no re-run, just DB replay).

Configure with environment variables:
  - ``COLMILLO_API_URL`` (default ``http://localhost:8000``)
  - ``COLMILLO_API_KEY`` (required, sent as ``X-API-Key``)
"""

from __future__ import annotations

import json
from typing import Any

import streamlit as st

from services.ui.api_client import APIClientConfig, APIError, PicksAPIClient


PAGES = ("Generate", "History")
FIXTURE_PROVIDERS = ("auto", "api-football", "llm")


@st.cache_resource(show_spinner=False)
def _get_client() -> PicksAPIClient:
    return PicksAPIClient(APIClientConfig.from_env())


def _config_warning_banner(config: APIClientConfig) -> None:
    if not config.api_key:
        st.warning(
            "COLMILLO_API_KEY is not set. The API will reject requests with 401.",
            icon="⚠️",
        )


def _render_pipeline_error(error: APIError) -> None:
    if isinstance(error.detail, dict) and "stage" in error.detail:
        st.error(
            f"Pipeline failed at stage **{error.detail.get('stage')}**: "
            f"{error.detail.get('message', 'unknown error')}",
            icon="🛑",
        )
    else:
        st.error(f"API returned {error.status_code}: {error.detail}", icon="🛑")


def _render_pick_payload(payload: dict[str, Any]) -> None:
    st.markdown(payload["report_markdown"])
    with st.expander("Raw scores"):
        st.json(payload.get("scores", []))
    if payload.get("trace"):
        with st.expander("Trace"):
            st.json(payload["trace"])
    if payload.get("match_inputs") is not None:
        with st.expander("Match inputs"):
            st.json(payload["match_inputs"])


def render_generate_page(client: PicksAPIClient) -> None:
    st.title("Generate Pick Report")
    st.caption("Submit a match query to run the deterministic scoring pipeline.")

    with st.form("generate_pick"):
        match_query = st.text_input(
            "Match query",
            value="juve - milan today",
            help="Format: 'home - away today|tomorrow|YYYY-MM-DD'.",
        )
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            league = st.text_input("League (optional)", value="")
            league_id = st.text_input("League ID (optional)", value="")
        with col_b:
            season = st.text_input("Season (optional)", value="")
            top_n = st.slider("Top N", min_value=1, max_value=5, value=5)
        with col_c:
            fixture_provider = st.selectbox("Fixture provider", FIXTURE_PROVIDERS, index=0)
            allow_fallback = st.checkbox("Allow deterministic fallback", value=False)

        with st.expander("LLM enrichment (optional)"):
            use_llm = st.checkbox("Enable LLM enrichment", value=False)
            llm_provider = st.text_input("LLM provider", value="", disabled=not use_llm)
            llm_model = st.text_input("LLM model", value="", disabled=not use_llm)

        submitted = st.form_submit_button("Generate", type="primary")

    if not submitted:
        return

    payload: dict[str, Any] = {
        "match_query": match_query.strip(),
        "top_n": int(top_n),
        "fixture_provider": fixture_provider,
        "allow_deterministic_fallback": bool(allow_fallback),
    }
    if league.strip():
        payload["league"] = league.strip()
    if league_id.strip():
        payload["league_id"] = league_id.strip()
    if season.strip():
        payload["season"] = season.strip()
    if use_llm:
        payload["use_llm"] = True
        if llm_provider.strip():
            payload["llm_provider"] = llm_provider.strip()
        if llm_model.strip():
            payload["llm_model"] = llm_model.strip()

    with st.spinner("Running pick pipeline…"):
        try:
            result = client.create_pick(payload)
        except APIError as exc:
            _render_pipeline_error(exc)
            return
        except Exception as exc:  # network / connection errors
            st.error(f"Failed to reach API: {exc}", icon="🛑")
            return

    st.success(f"Pick saved as id `{result.get('id', '?')}`.", icon="✅")
    _render_pick_payload(result)


def _format_history_row(item: dict[str, Any]) -> str:
    parts = [item.get("created_at", ""), item.get("match_query", "")]
    competition = item.get("competition")
    if competition:
        parts.append(f"[{competition}]")
    fixture_status = item.get("fixture_status")
    if fixture_status:
        parts.append(f"fixture={fixture_status}")
    llm_status = item.get("llm_status")
    if llm_status and llm_status != "not_requested":
        parts.append(f"llm={llm_status}")
    return " · ".join(str(part) for part in parts if part)


def render_history_page(client: PicksAPIClient) -> None:
    st.title("Pick History")
    st.caption("Recent pipeline runs persisted in the API database.")

    limit = st.sidebar.slider("Page size", min_value=5, max_value=50, value=20, step=5)
    page = st.session_state.get("history_page", 0)
    nav_prev, nav_next = st.sidebar.columns(2)
    if nav_prev.button("← Prev", disabled=page == 0):
        st.session_state["history_page"] = max(0, page - 1)
        st.rerun()
    if nav_next.button("Next →"):
        st.session_state["history_page"] = page + 1
        st.rerun()

    offset = page * limit
    try:
        listing = client.list_picks(limit=limit, offset=offset)
    except APIError as exc:
        _render_pipeline_error(exc)
        return
    except Exception as exc:
        st.error(f"Failed to reach API: {exc}", icon="🛑")
        return

    items: list[dict[str, Any]] = listing.get("items", [])
    if not items:
        st.info("No picks yet on this page. Generate one from the Generate tab.")
        return

    options = {item["id"]: _format_history_row(item) for item in items}
    selected_id = st.radio(
        f"Showing {len(items)} item(s) · offset {offset}",
        options=list(options.keys()),
        format_func=lambda pid: options[pid],
        index=0,
    )

    try:
        detail = client.get_pick(selected_id)
    except APIError as exc:
        _render_pipeline_error(exc)
        return

    st.subheader(detail.get("match_query", ""))
    st.caption(
        f"id `{detail['id']}` · created {detail.get('created_at')} · "
        f"latency {detail.get('latency_ms')} ms"
    )
    with st.expander("Original request"):
        st.code(json.dumps(detail.get("request", {}), indent=2), language="json")
    st.markdown(detail.get("report_markdown", ""))
    if detail.get("trace"):
        with st.expander("Trace"):
            st.json(detail["trace"])


def main() -> None:
    st.set_page_config(page_title="Colmillo-Picks", layout="wide")
    config = APIClientConfig.from_env()
    _config_warning_banner(config)
    page = st.sidebar.radio("Page", PAGES, index=0)
    client = _get_client()
    if page == "Generate":
        render_generate_page(client)
    else:
        render_history_page(client)


if __name__ == "__main__":  # pragma: no cover - streamlit entry point
    main()
