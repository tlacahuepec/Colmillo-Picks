#!/usr/bin/env python3
"""Render top soccer prop picks into a standardized report."""

from __future__ import annotations

import argparse
import json
from typing import Any


def render_report(scored_props: list[dict[str, Any]], top_n: int = 5) -> str:
    """Render a markdown report for top picks.

    Placeholder interface for future deterministic report rendering.
    """
    header = "# Soccer Prop Pick Report\n\n"
    body = f"Generated placeholder report with top_n={top_n}.\n"
    top_rows = scored_props[:top_n]
    return header + body + f"Input rows: {len(scored_props)}\nRendered rows: {len(top_rows)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render soccer prop pick report.")
    parser.add_argument("--top-n", type=int, default=5, help="Number of picks to render")
    parser.add_argument(
        "--input-json",
        default="[]",
        help="Serialized scored props payload",
    )
    args = parser.parse_args()

    scored_props = json.loads(args.input_json)
    report = render_report(scored_props, top_n=args.top_n)
    print(report)


if __name__ == "__main__":
    main()
