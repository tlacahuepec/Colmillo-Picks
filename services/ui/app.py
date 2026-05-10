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

    with st.spinner("Submitting pick request…"):
        try:
            accepted = client.create_pick(payload)
        except APIError as exc:
            _render_pipeline_error(exc)
            return
        except Exception as exc:  # network / connection errors
            st.error(f"Failed to reach API: {exc}", icon="\U0001f6d1")
            return

    pick_id = accepted.get("id", "")
    st.info(f"Pick `{pick_id}` accepted. Waiting for pipeline to finish…", icon="\u23f3")
    progress_box = st.empty()
    try:
        with st.spinner("Running pick pipeline…"):
            final = client.wait_for_pick(
                pick_id, timeout_seconds=180.0, poll_interval_seconds=1.5
            )
    except APIError as exc:
        _render_pipeline_error(exc)
        return
    except Exception as exc:
        st.error(f"Pipeline status polling failed: {exc}", icon="\U0001f6d1")
        return
    finally:
        progress_box.empty()

    if final.get("status") == "failed":
        st.error(
            f"Pipeline failed at stage **{final.get('error_stage')}**: "
            f"{final.get('error_message', 'unknown error')}",
            icon="\U0001f6d1",
        )
        return

    try:
        detail = client.get_pick(pick_id)
    except APIError as exc:
        _render_pipeline_error(exc)
        return

    st.success(f"Pick saved as id `{pick_id}`.", icon="\u2705")
    _render_pick_payload(detail)


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
        f"id `{detail['id']}` \u00b7 status `{detail.get('status', '?')}` \u00b7 "
        f"created {detail.get('created_at')} \u00b7 latency {detail.get('latency_ms')} ms"
    )
    if detail.get("status") == "failed":
        st.error(
            f"Pipeline failed at stage **{detail.get('error_stage')}**: "
            f"{detail.get('error_message', 'unknown error')}",
            icon="\U0001f6d1",
        )
    with st.expander("Original request"):
        st.code(json.dumps(detail.get("request", {}), indent=2), language="json")
    if detail.get("report_markdown"):
        st.markdown(detail["report_markdown"])
    if detail.get("trace"):
        with st.expander("Trace"):
            st.json(detail["trace"])

    if detail.get("status") == "success":
        _render_outcomes_section(client, detail)

    _render_hit_rate_panel(client)


def _render_outcomes_section(client: PicksAPIClient, detail: dict[str, Any]) -> None:
    """Outcome capture form + a list of previously recorded outcomes."""
    st.markdown("---")
    st.subheader("Outcomes")

    pick_id = detail["id"]
    scores = detail.get("scores") or []

    try:
        existing = client.get_outcomes(pick_id).get("items", [])
    except APIError as exc:
        _render_pipeline_error(exc)
        existing = []

    if existing:
        st.caption(f"{len(existing)} outcome(s) already recorded.")
        st.table(
            [
                {
                    "rank": item["rank"],
                    "player": item["player"],
                    "market": item["market"],
                    "result": item["result"],
                    "recorded_at": item["recorded_at"],
                }
                for item in existing
            ]
        )

    if not scores:
        st.info("No scored picks to grade yet.")
        return

    with st.form(f"outcomes-{pick_id}"):
        st.caption("Grade each pick after the match settles.")
        rows: list[dict[str, Any]] = []
        for entry in scores:
            rank = int(entry.get("rank", len(rows) + 1))
            player = str(entry.get("player", entry.get("name", "unknown")))
            market = str(entry.get("market", entry.get("prop", "unknown")))
            result = st.selectbox(
                f"#{rank} \u00b7 {player} \u00b7 {market}",
                options=("win", "loss", "push", "void"),
                index=0,
                key=f"outcome-{pick_id}-{rank}",
            )
            rows.append({"rank": rank, "player": player, "market": market, "result": result})
        submitted = st.form_submit_button("Save outcomes", type="primary")

    if submitted:
        try:
            client.record_outcomes(pick_id, rows)
        except APIError as exc:
            _render_pipeline_error(exc)
            return
        st.success("Outcomes saved.", icon="\u2705")
        st.rerun()


def _render_hit_rate_panel(client: PicksAPIClient) -> None:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Hit rate")
    try:
        summary = client.get_hit_rate()
    except APIError as exc:
        st.sidebar.error(f"Hit-rate fetch failed: {exc.detail}")
        return
    totals = summary.get("totals", {})
    decided = summary.get("decided", 0)
    rate = summary.get("hit_rate")
    st.sidebar.metric(
        "Win rate",
        f"{rate * 100:.1f}%" if rate is not None else "\u2014",
        f"{totals.get('win', 0)}W / {totals.get('loss', 0)}L of {decided}",
    )
    if totals.get("push") or totals.get("void"):
        st.sidebar.caption(
            f"push: {totals.get('push', 0)} \u00b7 void: {totals.get('void', 0)}"
        )


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
