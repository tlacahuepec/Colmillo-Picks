---
name: soccer-prop-picks
description: Analyze soccer match player prop opportunities focused on passes and shots markets. Trigger this skill when the user asks for soccer match prop analysis, player passes/shots over-under picks, or confidence-ranked soccer player prop recommendations.
---

# Soccer Prop Picks

Use this skill to produce deterministic, factor-based soccer player prop picks for passes and shots markets.

## Workflow

1. Collect match metadata and market inputs with `scripts/collect_match_inputs.py`.
2. Read domain references as needed:
   - `references/match-context.md`
   - `references/player-role-heuristics.md`
   - `references/market-logic.md`
3. Score candidate player props with `scripts/score_player_props.py`.
4. Render a final report with `scripts/render_pick_report.py`.

## Required Output Contract

Always return exactly **top 5 player picks** and include for each pick:

1. **Player + market** (e.g., passes or shots line)
2. **Direction**: Over or Under
3. **Confidence**: High / Medium / Low
4. **Rationale** tied to listed factors from references:
   - match context (home/away, weather, competition format)
   - player role and minutes expectation
   - market logic and implied probability checks

## Quality Checks

- Ensure rationale cites at least one match-context factor and one player-role factor.
- Reject picks if implied probability sanity checks fail.
- Prefer transparent assumptions when data is incomplete.
