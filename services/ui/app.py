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
import re
import sys
from datetime import date as _date, datetime as _datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_REPO_ROOT / ".env")

import streamlit as st  # noqa: E402

from services.ui.api_client import APIClientConfig, APIError, PicksAPIClient, SlateTimeoutError  # noqa: E402
from services.ui.best_today_helpers import (  # noqa: E402
    build_slate_payload,
    format_match_run_summary,
    format_slate_candidate_row,
    render_no_candidates_message,
    render_partial_failure_summary,
)


PAGES = ("Generate", "History", "Best Today")


def _format_utc_to_local(utc_str: str) -> str:
    if not utc_str:
        return utc_str
    try:
        dt = _datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
        local_dt = dt.astimezone()
        return local_dt.strftime("%b %d, %I:%M %p")
    except (ValueError, TypeError):
        return utc_str


def _construct_match_query(home_team: str, away_team: str, date: str) -> str:
    home = home_team.strip() if home_team else ""
    away = away_team.strip() if away_team else ""
    date_clean = date.strip() if date else ""

    if not home:
        raise ValueError("home team is required")
    if not away:
        raise ValueError("away team is required")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_clean):
        raise ValueError(f"date must be YYYY-MM-DD format, got: {date_clean!r}")

    return f"{home} - {away} {date_clean}"


def _build_pick_payload(
    sport: str,
    home_team: str,
    away_team: str,
    date: _date,
    top_n: int,
    use_llm_enrichment: bool,
    allow_fallback: bool,
    markets: list[str] | None = None,
    league: str | None = None,
) -> dict[str, Any]:
    home = home_team.strip() if home_team else ""
    away = away_team.strip() if away_team else ""

    if not home:
        raise ValueError("home team is required")
    if not away:
        raise ValueError("away team is required")

    payload: dict[str, Any] = {
        "sport": sport,
        "event_date": date.isoformat(),
        "home_team": home,
        "away_team": away,
        "top_n": int(top_n),
        "allow_deterministic_fallback": bool(allow_fallback),
    }

    if use_llm_enrichment:
        payload["use_llm"] = True
    if markets:
        payload["markets"] = markets
    if league:
        payload["league"] = league

    return payload


def _build_match_discovery_payload(
    *,
    date: _date,
    sports: list[str],
    limit_per_sport: int,
) -> dict[str, Any]:
    normalized_sports = [
        sport.strip().lower()
        for sport in sports
        if sport and sport.strip()
    ]
    if not normalized_sports:
        raise ValueError("at least one sport is required")
    return {
        "date": date.isoformat(),
        "sports": normalized_sports,
        "limit_per_sport": int(limit_per_sport),
    }


def _build_payload_from_suggested_match(
    suggested_match: dict[str, Any] | None,
    *,
    top_n: int,
    use_llm_enrichment: bool,
    allow_fallback: bool,
) -> dict[str, Any]:
    if not suggested_match:
        raise ValueError("suggested match is required")

    event_date = str(suggested_match.get("event_date", "")).strip()
    try:
        parsed_date = _date.fromisoformat(event_date)
    except ValueError:
        raise ValueError(f"suggested match date must be YYYY-MM-DD, got: {event_date!r}") from None

    return _build_pick_payload(
        sport=str(suggested_match.get("sport", "")).strip().lower(),
        home_team=str(suggested_match.get("home_team", "")).strip(),
        away_team=str(suggested_match.get("away_team", "")).strip(),
        date=parsed_date,
        top_n=top_n,
        use_llm_enrichment=use_llm_enrichment,
        allow_fallback=allow_fallback,
        league=suggested_match.get("league") or None,
    )


def _format_suggested_match(match: dict[str, Any]) -> str:
    sport = str(match.get("sport", "")).strip().title() or "Sport"
    home = str(match.get("home_team", "")).strip() or "Unknown"
    away = str(match.get("away_team", "")).strip() or "Unknown"
    competition = match.get("competition") or match.get("league") or "competition unknown"
    kickoff = _format_utc_to_local(match.get("kickoff_utc") or "") or "kickoff unknown"
    importance = match.get("importance") or "importance unknown"
    data_quality = match.get("data_quality") if isinstance(match.get("data_quality"), dict) else {}
    confidence = data_quality.get("confidence", "unknown")
    missing_fields = data_quality.get("missing_fields") or []
    missing = ",".join(str(field) for field in missing_fields) if missing_fields else "none"
    source_count = data_quality.get("source_count", len(match.get("sources") or []))

    return (
        f"{sport} | {home} vs {away} | {competition} | {kickoff} | "
        f"importance={importance} | confidence={confidence} | "
        f"missing={missing} | sources={source_count}"
    )


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


def _clear_availability_cache() -> None:
    for key in list(st.session_state.keys()):
        if str(key).startswith("availability_badges_") or str(key).startswith("availability_"):
            del st.session_state[key]


def _submit_pick_and_render(client: PicksAPIClient, payload: dict[str, Any]) -> None:
    _clear_availability_cache()

    with st.spinner("Submitting pick request..."):
        try:
            accepted = client.create_pick(payload)
        except APIError as exc:
            _render_pipeline_error(exc)
            return
        except Exception as exc:
            st.error(f"Failed to reach API: {exc}", icon="\U0001f6d1")
            return

    pick_id = accepted.get("id", "")
    st.info(f"Pick `{pick_id}` accepted. Waiting for pipeline to finish...", icon="\u23f3")
    progress_box = st.empty()
    try:
        with st.spinner("Running pick pipeline..."):
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
    _render_availability_section(client, pick_id)


def _render_availability_section(client: PicksAPIClient, pick_id: str) -> None:
    from services.ui.availability_badges import BadgeStatus, classify_badge

    st.subheader("Availability Check")

    platforms = st.multiselect(
        "Platforms",
        options=["prizepicks"],
        default=["prizepicks"],
        key=f"platforms_{pick_id}",
    )

    col_refresh, col_status = st.columns([1, 3])
    with col_refresh:
        refresh = st.button("Refresh Availability", key=f"refresh_{pick_id}")

    cache_key = f"availability_{pick_id}"
    if refresh or cache_key not in st.session_state:
        try:
            result = client.check_availability(pick_id, platforms=platforms or None)
            st.session_state[cache_key] = result
        except Exception as exc:
            st.warning(f"Availability check failed: {exc}", icon="\u26a0\ufe0f")
            return

    avail_data = st.session_state.get(cache_key)
    if not avail_data:
        return

    if avail_data.get("fallback_mode"):
        st.info(f"Fallback mode: {avail_data.get('fallback_reason', 'unknown')}", icon="\u2753")
        return

    badges = avail_data.get("badges", [])
    if not badges:
        st.info("No availability data for this pick.", icon="\u2753")
        return

    for badge in badges:
        status = classify_badge(
            platform_status=badge.get("status", "unknown"),
            platform_line=badge.get("platform_line"),
            recommended_line=badge.get("line", 0),
        )
        player = badge.get("player", "")
        market = badge.get("market", "")
        platform = badge.get("platform", "")

        if status == BadgeStatus.AVAILABLE:
            url = badge.get("url")
            link_text = f" [Open]({url})" if url else ""
            st.success(f"{status.icon} **{player}** ({market}) — Available on {platform}{link_text}")
        elif status == BadgeStatus.LINE_DIFFERS:
            plat_line = badge.get("platform_line", "?")
            rec_line = badge.get("line", "?")
            st.warning(f"{status.icon} **{player}** ({market}) — Line differs: {plat_line} vs recommended {rec_line}")
        elif status == BadgeStatus.UNAVAILABLE:
            st.error(f"{status.icon} **{player}** ({market}) — Not available on {platform}")
        else:
            st.info(f"{status.icon} **{player}** ({market}) — Could not check {platform}")


def _render_match_suggestions(client: PicksAPIClient) -> bool:
    st.subheader("Match Suggestions")

    col_date, col_sports, col_limit = st.columns([1, 2, 1])
    with col_date:
        discovery_date = st.date_input(
            "Suggestion date",
            value=st.session_state.get("gen_date", _date.today()),
            key="discover_date",
        )
    with col_sports:
        discovery_sports = st.multiselect(
            "Suggestion sports",
            options=["Soccer", "Basketball", "Baseball"],
            default=["Soccer", "Basketball", "Baseball"],
            key="discover_sports",
        )
    with col_limit:
        limit_per_sport = st.slider(
            "Matches per sport",
            min_value=1,
            max_value=5,
            value=3,
            key="discover_limit",
        )

    run_col_n, run_col_explain, run_col_fallback = st.columns(3)
    with run_col_n:
        suggestion_top_n = st.slider(
            "Suggestion top N",
            min_value=1,
            max_value=5,
            value=5,
            key="suggestion_top_n",
        )
    with run_col_explain:
        suggestion_explain = st.checkbox(
            "Suggestion explanations",
            value=False,
            key="suggestion_explain",
        )
    with run_col_fallback:
        suggestion_fallback = st.checkbox(
            "Suggestion fallback",
            value=False,
            key="suggestion_fallback",
        )

    if st.button("Find today's matches", key="find_todays_matches"):
        try:
            payload = _build_match_discovery_payload(
                date=discovery_date,
                sports=discovery_sports,
                limit_per_sport=limit_per_sport,
            )
            with st.spinner("Discovering matches..."):
                st.session_state["match_discovery_results"] = client.discover_matches(**payload)
            st.session_state.pop("match_discovery_error", None)
        except APIError as exc:
            st.session_state["match_discovery_error"] = f"API returned {exc.status_code}: {exc.detail}"
        except Exception as exc:
            st.session_state["match_discovery_error"] = str(exc)

    if st.session_state.get("match_discovery_error"):
        st.error(st.session_state["match_discovery_error"], icon="\U0001f6d1")

    discovery = st.session_state.get("match_discovery_results")
    if not discovery:
        return False

    results = discovery.get("results", {})
    for sport, sport_result in results.items():
        st.markdown(f"**{str(sport).title()}**")
        if sport_result.get("error"):
            st.warning(str(sport_result["error"]), icon="\u26a0\ufe0f")
        matches = sport_result.get("matches") or []
        if not matches:
            st.info("No suggested matches returned.")
            continue
        for index, match in enumerate(matches):
            text_col, run_col = st.columns([5, 1])
            with text_col:
                st.caption(_format_suggested_match(match))
            with run_col:
                if st.button("Run", key=f"run_suggested_{sport}_{index}"):
                    try:
                        payload = _build_payload_from_suggested_match(
                            match,
                            top_n=suggestion_top_n,
                            use_llm_enrichment=suggestion_explain,
                            allow_fallback=suggestion_fallback,
                        )
                    except ValueError as exc:
                        st.error(str(exc), icon="\u26a0\ufe0f")
                        return True
                    _submit_pick_and_render(client, payload)
                    return True

    return False


def render_generate_page(client: PicksAPIClient) -> None:
    st.title("Generate Pick Report")
    st.caption("Enter match details to generate prop pick recommendations.")

    if _render_match_suggestions(client):
        return

    # Explicit widget keys prevent Streamlit from resetting values when
    # the baseball conditional block adds/removes widgets between reruns.
    with st.form("generate_pick"):
        col_sport, col_date = st.columns(2)
        with col_sport:
            sport = st.selectbox(
                "Sport",
                options=["Soccer", "Basketball", "Baseball"],
                index=0,
                help="Select the sport for prop analysis.",
                key="gen_sport",
            )
        with col_date:
            date = st.date_input("Match date", value=_date.today(), key="gen_date")

        _TEAM_HINTS: dict[str, tuple[str, str]] = {
            "soccer": ("e.g. Bayern Munich", "e.g. Stuttgart"),
            "basketball": ("e.g. Boston Celtics", "e.g. Los Angeles Lakers"),
            "baseball": ("e.g. New York Yankees", "e.g. Boston Red Sox"),
        }
        home_hint, away_hint = _TEAM_HINTS.get(sport.lower(), ("", ""))

        col_home, col_away = st.columns(2)
        with col_home:
            home_team = st.text_input("Home team", value="", help=home_hint, key="gen_home")
        with col_away:
            away_team = st.text_input("Away team", value="", help=away_hint, key="gen_away")

        _BASEBALL_MARKETS = [
            "hits", "total_bases", "runs", "rbi",
            "home_runs", "strikeouts", "walks", "pitcher_outs",
        ]
        selected_markets: list[str] = []
        selected_league: str | None = None

        if sport.lower() == "baseball":
            col_league, col_markets = st.columns(2)
            with col_league:
                st.selectbox("League", options=["MLB"], index=0, disabled=True, key="gen_league")
                selected_league = "mlb"
            with col_markets:
                selected_markets = st.multiselect(
                    "Markets",
                    options=_BASEBALL_MARKETS,
                    default=_BASEBALL_MARKETS,
                    help="Select MLB prop markets to analyze",
                    key="gen_markets",
                )

        col_n, col_explain, col_fallback = st.columns(3)
        with col_n:
            top_n = st.slider("Top N picks", min_value=1, max_value=5, value=5, key="gen_top_n")
        with col_explain:
            add_explanations = st.checkbox(
                "Add pick explanations", value=False, help="LLM adds rationale to each pick",
                key="gen_explain",
            )
        with col_fallback:
            allow_fallback = st.checkbox(
                "Allow fallback", value=False, help="Return deterministic picks if pipeline fails",
                key="gen_fallback",
            )

        submitted = st.form_submit_button("Generate", type="primary")

    if not submitted:
        return

    try:
        payload = _build_pick_payload(
            sport=sport.lower(),
            home_team=home_team,
            away_team=away_team,
            date=date,
            top_n=top_n,
            use_llm_enrichment=add_explanations,
            allow_fallback=allow_fallback,
            markets=selected_markets or None,
            league=selected_league,
        )
        _submit_pick_and_render(client, payload)
        return
    except ValueError as exc:
        st.error(str(exc), icon="⚠️")
        return

def _format_history_row(item: dict[str, Any]) -> str:
    parts = [item.get("created_at", ""), item.get("match_query", "")]
    sport = item.get("sport")
    if sport:
        parts.append(f"[{sport}]")
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

    sport_filter = st.sidebar.selectbox(
        "Filter by sport",
        options=["All", "Soccer", "Basketball", "Baseball"],
        index=0,
    )
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
    sport_param = sport_filter.lower() if sport_filter != "All" else None
    try:
        listing = client.list_picks(limit=limit, offset=offset, sport=sport_param)
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


def render_best_today_page(client: PicksAPIClient) -> None:
    st.title("Best Today")
    st.caption("Generate a ranked cross-sport slate of today's best prop picks.")

    with st.form("best_today_form"):
        col_date, col_sports = st.columns([1, 2])
        with col_date:
            slate_date = st.date_input("Date", value=_date.today(), key="slate_date")
        with col_sports:
            slate_sports = st.multiselect(
                "Sports",
                options=["Soccer", "Basketball", "Baseball"],
                default=["Soccer", "Basketball", "Baseball"],
                key="slate_sports",
            )

        col_max, col_top = st.columns(2)
        with col_max:
            max_matches = st.slider(
                "Max matches per sport", min_value=1, max_value=5, value=3, key="slate_max_matches"
            )
        with col_top:
            top_n = st.slider(
                "Top N candidates", min_value=1, max_value=20, value=10, key="slate_top_n"
            )

        submitted = st.form_submit_button("Generate Best Today", type="primary")

    if not submitted:
        return

    normalized_sports = [s.lower() for s in slate_sports] if slate_sports else []
    try:
        payload = build_slate_payload(
            date=slate_date.isoformat(),
            sports=normalized_sports,
            max_matches_per_sport=max_matches,
            top_n=top_n,
        )
    except ValueError as exc:
        st.error(str(exc), icon="\u26a0\ufe0f")
        return

    with st.spinner("Submitting slate request..."):
        try:
            accepted = client.create_slate(payload)
        except APIError as exc:
            st.error(f"API error {exc.status_code}: {exc.detail}", icon="\U0001f6d1")
            return
        except Exception as exc:
            st.error(f"Failed to reach API: {exc}", icon="\U0001f6d1")
            return

    slate_id = accepted.get("id", "")
    st.info(f"Slate `{slate_id}` accepted. Running pipelines...", icon="\u23f3")

    try:
        with st.spinner("Waiting for slate to complete..."):
            client.wait_for_slate(slate_id, timeout_seconds=300.0, poll_interval_seconds=2.0)
    except SlateTimeoutError:
        st.warning("Slate generation timed out. Showing partial results.", icon="\u23f1\ufe0f")
    except APIError as exc:
        st.error(f"Status polling failed: {exc.detail}", icon="\U0001f6d1")
        return
    except Exception as exc:
        st.error(f"Polling error: {exc}", icon="\U0001f6d1")
        return

    try:
        detail = client.get_slate(slate_id)
    except APIError as exc:
        st.error(f"Failed to fetch slate detail: {exc.detail}", icon="\U0001f6d1")
        return

    _render_slate_results(detail)


def _render_slate_results(detail: dict[str, Any]) -> None:
    status = detail.get("status", "?")
    if status == "failed":
        st.error(
            f"Slate failed at stage **{detail.get('error_stage', '?')}**: "
            f"{detail.get('error_message', 'unknown error')}",
            icon="\U0001f6d1",
        )
        return

    st.success(f"Slate complete — status: **{status}**", icon="\u2705")

    with st.expander("Timing & Metadata", expanded=False):
        col_latency, col_discovery, col_matches = st.columns(3)
        with col_latency:
            st.metric("Total latency", f"{detail.get('latency_ms', '?')} ms")
        with col_discovery:
            st.metric("Discovery latency", f"{detail.get('discovery_latency_ms', '?')} ms")
        with col_matches:
            attempted = detail.get("matches_attempted", 0)
            succeeded = detail.get("matches_succeeded", 0)
            st.metric("Matches", f"{succeeded}/{attempted}")

    candidates = detail.get("candidates", [])
    match_runs = detail.get("match_runs", [])

    if not candidates:
        st.warning(render_no_candidates_message(), icon="\u26a0\ufe0f")
    else:
        st.subheader("Ranked Candidates")
        for candidate in candidates:
            st.text(format_slate_candidate_row(candidate))

    partial_failures = render_partial_failure_summary(match_runs)
    if partial_failures:
        st.subheader("Partial Failures")
        st.markdown(partial_failures)

    if match_runs:
        with st.expander("Match Run Details", expanded=False):
            for run in match_runs:
                st.text(format_match_run_summary(run))


def main() -> None:
    st.set_page_config(page_title="Colmillo-Picks", layout="wide")
    config = APIClientConfig.from_env()
    _config_warning_banner(config)
    page = st.sidebar.radio("Page", PAGES, index=0)
    client = _get_client()
    if page == "Generate":
        render_generate_page(client)
    elif page == "History":
        render_history_page(client)
    else:
        render_best_today_page(client)


if __name__ == "__main__":  # pragma: no cover - streamlit entry point
    main()
