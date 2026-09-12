"""Diagnostics presentation and safe local reports for the Streamlit UI."""

from __future__ import annotations

from datetime import datetime, time, timezone
from io import BytesIO
import json
import re
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import httpx
import streamlit as st

from services.ui.api_client import APIError, PicksAPIClient, PickTimeoutError


def safe_text(value: Any, default: str = "Unknown") -> str:
    """Display scalar diagnostic fields, never raw metadata or stack traces."""
    if value is None or isinstance(value, (dict, list, tuple)):
        return default
    text = str(value)
    if re.search(r"Traceback|stack[_ -]?trace|File \".+\", line \d+", text, re.I):
        return "Technical details are available in the diagnostic report."
    text = re.sub(r"https?://\S+", "[URL omitted]", text)
    text = re.sub(r"(?i)\bBearer\s+\S+", "Bearer [redacted]", text)
    text = re.sub(
        r"(?i)\b(?:[\w-]*(?:api[_-]?key|token|secret|password)|authorization|cookie)"
        r"\b[\"']?\s*[:=]\s*[^\n,;]+", "[credential redacted]", text,
    )
    return text[:2000]


def failure_info(error: Exception) -> tuple[str, str]:
    if isinstance(error, PickTimeoutError):
        return "polling_timeout", "The UI stopped waiting. The backend may still be running; check History or Diagnostics before submitting again."
    if isinstance(error, APIError):
        if error.status_code in (401, 403):
            return "authentication", "The API denied access. Check the UI API key configuration."
        if error.status_code == 404:
            return "not_found", "Diagnostics were not found. The operation may be older than the retained records."
        return "api_error", f"The API could not complete the request (HTTP {error.status_code}). Try Refresh."
    if isinstance(error, httpx.TimeoutException):
        return "timeout", "The API did not respond in time. Try Refresh."
    if isinstance(error, httpx.RequestError):
        return "connection", "The UI could not reach the API. Check the connection and try Refresh."
    return "unavailable", "The request could not be completed. Try Refresh."


def local_failure_report(error: Exception) -> bytes:
    """Allowlist only: no exception strings, URLs, credentials, or payloads."""
    category, explanation = failure_info(error)
    report = {
        "report_type": "ui_connection_failure",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "streamlit_ui",
        "category": category,
        "summary": explanation,
        "completeness": "Local UI report only; backend diagnostics were unavailable.",
    }
    if isinstance(error, APIError):
        report["http_status"] = error.status_code
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("report.json", json.dumps(report, indent=2))
    return output.getvalue()


def render_connection_failure(error: Exception, *, key: str) -> None:
    st.error(failure_info(error)[1])
    st.download_button(
        "Download local failure report", data=local_failure_report(error),
        file_name="ui-connection-report.zip", mime="application/zip", key=f"{key}_report",
    )


def _open_diagnostics(identifier: str) -> None:
    st.session_state["ui_page"] = "Diagnostics"
    st.session_state["diagnostics_pending_search"] = identifier


def render_diagnostics_link(record: dict[str, Any], *, key: str) -> None:
    identifier = record.get("operation_id") or record.get("id") or record.get("pick_id") or record.get("slate_id")
    if identifier:
        st.button(
            "View diagnostics", key=key, on_click=_open_diagnostics,
            args=(str(identifier),), help="Find diagnostics by operation, pick, or slate ID.",
        )


def completeness_text(value: Any) -> str:
    if isinstance(value, bool):
        return "Complete" if value else "Partial — some diagnostic records are missing."
    if isinstance(value, dict):
        # The contract allows structured completeness; do not dump arbitrary fields.
        if value.get("truncated") or value.get("has_more"):
            return "Partial — more events exist than this view includes. Download the report for a larger snapshot."
        status = value.get("status")
        if status in {"possibly_incomplete", "interrupted", "expired", "pruned", "truncated", "legacy_summary_only"}:
            explanations = {
                "possibly_incomplete": "Some diagnostic events may be missing because collection dropped events.",
                "interrupted": "The recording process stopped; the job's final outcome is unconfirmed.",
                "expired": "Detailed events expired; the retained summary may still be available.",
                "pruned": "Some events were removed to stay within the storage budget.",
                "truncated": "This operation reached the event limit; some details were omitted.",
                "legacy_summary_only": "Only the saved result is available; detailed diagnostics were not recorded.",
            }
            return explanations[status]
        if isinstance(value.get("complete"), bool):
            return completeness_text(value["complete"])
        if value.get("retention_may_apply"):
            return "Snapshot of retained events; older records may be unavailable."
        return safe_text(value.get("status"), "Completeness details are available in the report.")
    return safe_text(value, "Completeness was not reported.")


def operation_summary(operation: dict[str, Any], completeness: Any) -> str:
    outcome = safe_text(operation.get("outcome"), "unknown")
    explanations = {
        "success": "The operation completed successfully.",
        "failed": "The operation failed. Review the stages below to locate the failure.",
        "pending": "The operation is waiting to start. Refresh to check progress.",
        "running": "The operation is still running. Refresh to check progress.",
        "partial": "The operation finished with partial results. Review the stages below.",
        "no_picks": "Analysis completed, but no verified picks qualified.",
        "pending_data": "The operation is waiting for source data. Refresh to check progress.",
    }
    explanation = safe_text(operation.get("summary"), explanations.get(outcome, "Review the recorded stages below."))
    return "\n".join([
        f"Operation: {safe_text(operation.get('operation_id'))}",
        f"Service: {safe_text(operation.get('service'))} | Sport: {safe_text(operation.get('sport'))}",
        f"Match: {safe_text(operation.get('home_team'), '—')} vs {safe_text(operation.get('away_team'), '—')}",
        f"Outcome: {outcome} | Duration: {safe_text(operation.get('duration_ms'), '—')} ms",
        f"Started: {safe_text(operation.get('started_at'))} | Updated: {safe_text(operation.get('updated_at'))}",
        explanation,
        f"Completeness: {completeness_text(completeness)}",
    ])


def next_action(operation: dict[str, Any]) -> str:
    code = (operation.get("metadata") or {}).get("error_code")
    actions = {
        "timeout": "Try again later. If it repeats, download the report so the provider timing can be checked.",
        "rate_limited": "Wait before trying again; the provider is limiting requests.",
        "configuration_error": "Ask the app administrator to check the provider configuration and include this report.",
        "invalid_output": "Try once more. If validation keeps failing, download the report for investigation.",
        "missing_citations": "Verified sources were unavailable. Try again when more matchup information is published.",
        "fixture_not_found": "Check the teams and match date, then try again.",
        "storage_error": "Check History before submitting again, and share this report with the administrator.",
    }
    if code in actions:
        return actions[code]
    return {
        "running": "Refresh to check progress. Avoid submitting the same query again while it is running.",
        "queued": "The operation is waiting for a worker. Refresh to check progress.",
        "success": "No action is needed. You can download a report to keep a record.",
        "no_picks": "No verified picks qualified. Check the match date or try later when more data is available.",
        "partial": "Review the available results and failed stages before deciding whether to retry.",
    }.get(operation.get("outcome"), "Download the diagnostic ZIP and include it when reporting this problem.")


def _clear_cached_diagnostics() -> None:
    for key in ("diagnostics_listing", "diagnostics_detail", "diagnostics_health", "diagnostics_export"):
        st.session_state.pop(key, None)


def render_diagnostics_page(client: PicksAPIClient) -> None:
    st.title("Diagnostics")
    st.caption("Find an operation, read its stages, and download a report. Refresh manually to get updates.")
    pending = st.session_state.pop("diagnostics_pending_search", None)
    if pending is not None:
        st.session_state.update({
            "diag_operation_id": pending, "diag_since": None, "diag_sport": "All",
            "diag_outcome": "", "diag_service": "", "diagnostics_offset": 0,
        })
        _clear_cached_diagnostics()

    cols = st.columns(3)
    with cols[0]:
        since_date = st.date_input("Since date (UTC)", value=None, key="diag_since")
        sport = st.selectbox("Sport", ["All", "Soccer", "Basketball", "Baseball", "NFL"], key="diag_sport")
    with cols[1]:
        outcome = st.text_input("Outcome", key="diag_outcome", help="For example: success, failed, running, partial.")
        service = st.text_input("Service", key="diag_service")
    with cols[2]:
        identifier = st.text_input("Operation ID / pick ID / slate ID", key="diag_operation_id")
        limit = st.selectbox("Page size", [20, 50, 100], key="diag_limit")
    filters = {
        "sport": sport.lower() if sport != "All" else None,
        "outcome": outcome.strip() or None, "service": service.strip() or None,
        "operation_id": identifier.strip() or None,
        "since": datetime.combine(since_date, time.min, tzinfo=timezone.utc).isoformat() if since_date else None,
        "limit": limit,
    }
    if filters != st.session_state.get("diagnostics_filters"):
        st.session_state["diagnostics_filters"] = filters
        st.session_state["diagnostics_offset"] = 0
        _clear_cached_diagnostics()
    if st.button("Refresh diagnostics", key="diag_refresh"):
        _clear_cached_diagnostics()

    try:
        if "diagnostics_health" not in st.session_state:
            st.session_state["diagnostics_health"] = client.diagnostics_health()
        health = st.session_state["diagnostics_health"]
        st.caption(f"Diagnostics health: {safe_text(health.get('status'), 'Status not reported')}")
        counters = health.get("counters") or {}
        st.caption(
            f"Events waiting to save: {safe_text(health.get('queue_depth'), '—')} · "
            f"Dropped events: {safe_text(counters.get('dropped_events', 0))} · "
            f"Storage failures: {safe_text(counters.get('write_failures', 0))}"
        )
    except Exception as error:
        render_connection_failure(error, key="diag_health")

    offset = st.session_state.get("diagnostics_offset", 0)
    query = {**filters, "offset": offset}
    try:
        cached = st.session_state.get("diagnostics_listing")
        if cached is None or cached[0] != query:
            cached = (query, client.list_diagnostic_operations(**query))
            st.session_state["diagnostics_listing"] = cached
        items = cached[1].get("items", [])
    except Exception as error:
        render_connection_failure(error, key="diag_list")
        return

    prev, next_col = st.columns(2)
    if prev.button("Previous operations", disabled=offset == 0):
        st.session_state["diagnostics_offset"] = max(0, offset - limit)
        st.rerun()
    if next_col.button("Next operations", disabled=len(items) < limit):
        st.session_state["diagnostics_offset"] = offset + limit
        st.rerun()
    st.caption(f"Showing {len(items)} operations · offset {offset}")
    if not items:
        st.info("No operations match these filters. Older picks or slates may have no diagnostics.")
        return

    by_id = {item["operation_id"]: item for item in items}
    selected = st.selectbox(
        "Operation", list(by_id), key="diag_selected",
        format_func=lambda oid: " · ".join(safe_text(by_id[oid].get(field), "—") for field in (
            "started_at", "service", "sport", "home_team", "away_team", "outcome", "operation_id",
        )),
    )
    try:
        cached_detail = st.session_state.get("diagnostics_detail")
        if cached_detail is None or cached_detail[0] != selected:
            cached_detail = (selected, client.get_diagnostic_operation(selected))
            st.session_state["diagnostics_detail"] = cached_detail
            st.session_state.pop("diagnostics_export", None)
        detail = cached_detail[1]
    except Exception as error:
        render_connection_failure(error, key="diag_detail")
        return

    operation = detail.get("operation") or by_id[selected]
    completeness = detail.get("completeness", operation.get("completeness"))
    st.subheader("Operation detail")
    st.caption("Use the copy button in this summary to copy it.")
    st.code(operation_summary(operation, completeness), language=None)
    st.markdown("**What to do next:** " + next_action(operation))
    st.subheader("Stages")
    events = detail.get("events") or []
    if not events:
        st.info("No stage events were recorded. Check the completeness information above.")
    for event in events:
        stage = safe_text(event.get("stage"), "Operation").replace("_", " ")
        name = safe_text(event.get("event"), "Recorded event").replace("_", " ")
        st.text(f"{stage}: {name}")
        st.caption(
            f"{safe_text(event.get('ts'), '—')} · {safe_text(event.get('level'), 'info')} · "
            f"{safe_text(event.get('outcome'), '—')} · {safe_text(event.get('duration_ms'), '—')} ms"
        )
        metadata = event.get("metadata") or {}
        if metadata.get("error_code"):
            st.caption("Recorded cause: " + safe_text(metadata["error_code"]).replace("_", " "))
        if metadata.get("reason_counts"):
            st.caption("Excluded inputs: " + ", ".join(
                f"{safe_text(reason).replace('_', ' ')}: {safe_text(count)}"
                for reason, count in list(metadata["reason_counts"].items())[:20]
            ))

    if st.button("Prepare diagnostic ZIP", key="diag_prepare_export"):
        st.session_state.pop("diagnostics_export", None)
        try:
            st.session_state["diagnostics_export"] = (selected, client.export_diagnostic_operation(selected))
        except Exception as error:
            render_connection_failure(error, key="diag_export")
    export = st.session_state.get("diagnostics_export")
    if export is not None and export[0] == selected:
        st.download_button(
            "Download diagnostic ZIP", data=export[1], file_name="diagnostic-report.zip",
            mime="application/zip", key="diag_download",
        )
