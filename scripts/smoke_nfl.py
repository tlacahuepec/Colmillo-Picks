"""Run one real NFL analysis without writing to the app databases."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "skills" / "soccer-prop-picks" / "scripts"))
    from dotenv import load_dotenv
    from match_discovery import MatchDiscoveryClient
    from nfl_collection import NflCollector
    from nfl_module import NflModule
    from render_nfl_report import render_nfl_report

    load_dotenv(root / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--home")
    parser.add_argument("--away")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--timezone", default="America/Chicago")
    parser.add_argument("--output-dir", default=str(root / "data" / "nfl-smoke"))
    args = parser.parse_args()
    if bool(args.home) != bool(args.away):
        parser.error(
            "Provide both --home and --away, or neither to discover a matchup."
        )
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    try:
        configured = MatchDiscoveryClient.from_env(
            provider=args.provider, model=args.model, max_output_tokens=16000
        )
        if not args.home:
            print("Discovering an upcoming NFL matchup...", flush=True)
            result = configured.discover_matches(
                date_utc=args.date,
                sports=["nfl"],
                limit_per_sport=1,
                timezone=args.timezone,
            )
            (output / "discovery.json").write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            matches = result["results"]["nfl"]["matches"]
            if not matches:
                print(
                    "No upcoming NFL fixture was verified. See discovery.json for details."
                )
                return 2
            args.home, args.away = matches[0]["home_team"], matches[0]["away_team"]
        print(f"Collecting {args.home} v {args.away} on {args.date}...", flush=True)
        module = NflModule(
            collector=NflCollector(configured.client, timezone_name=args.timezone)
        )
        data = module.collect_inputs(
            home_team=args.home, away_team=args.away, match_date=args.date
        )
        scores = module.score(data)
        (output / "analysis.json").write_text(
            json.dumps({"inputs": data, "scores": scores}, indent=2), encoding="utf-8"
        )
        (output / "report.md").write_text(
            render_nfl_report(scores, data), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "picks": len(scores),
                    "offers": len(data.get("offers", [])),
                    "grounding_sources": len(data.get("grounding_sources", [])),
                    "provider_statuses": data.get("provider_statuses", {}),
                    "provider_errors": data.get("provider_errors", {}),
                    "exclusions": data.get("exclusions", []),
                },
                indent=2,
            )
        )
        return 0 if scores else 2
    except Exception as exc:
        print(
            f"Live NFL smoke could not complete ({type(exc).__name__}). Check provider credentials and network access."
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
