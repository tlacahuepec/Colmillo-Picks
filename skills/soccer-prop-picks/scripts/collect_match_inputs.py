#!/usr/bin/env python3
"""Collect structured soccer match inputs for downstream prop scoring."""

from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass
class MatchInputRequest:
    match_id: str
    competition: str


def collect_inputs(request: MatchInputRequest) -> dict:
    """Return normalized match inputs.

    Placeholder interface for future deterministic data collection.
    """
    return {
        "match_id": request.match_id,
        "competition": request.competition,
        "status": "placeholder",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect soccer match inputs.")
    parser.add_argument("match_id", help="Provider match identifier")
    parser.add_argument("competition", help="Competition code/name")
    args = parser.parse_args()

    payload = collect_inputs(MatchInputRequest(args.match_id, args.competition))
    print(payload)


if __name__ == "__main__":
    main()
