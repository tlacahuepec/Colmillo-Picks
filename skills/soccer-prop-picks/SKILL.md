---
name: soccer-prop-picks
description: Analyze soccer match player prop opportunities focused on passes and shots markets. Trigger this skill when the user asks for soccer match prop analysis, player passes/shots over-under picks, or confidence-ranked soccer player prop recommendations.
---

# Soccer Prop Picks

Use this skill to produce deterministic, factor-based soccer player prop picks for passes and shots markets.

## Workflow Phases

### 1) Intake

1. Collect match metadata and market inputs with `scripts/collect_match_inputs.py`.
2. Read domain references as needed:
   - `references/match-context.md`
   - `references/player-role-heuristics.md`
   - `references/market-logic.md`
   - `references/decision-playbook.md`

### 2) Validation

1. Confirm the match input payload includes required lineup, injury/suspension, weather, and market timestamp fields.
2. If critical fields are missing, carry explicit assumptions forward and mark those assumptions in the final report.
3. Keep all eligibility and recommendation gating aligned with `scripts/score_player_props.py` outputs.

### 3) Scoring

1. Score candidate player props with `scripts/score_player_props.py`.
2. Do not restate or invent numeric thresholds in prose; use model outputs and flags from the scorer.

### 4) Contradiction Checks

1. Verify rationale coherence against `references/decision-playbook.md` checkpoints.
2. Reject or downgrade picks when market agreement sanity fails or context signals conflict materially.

### 5) Final Recommendation Formatting

1. Render a final report with `scripts/render_pick_report.py`.
2. Ensure output sections include assumptions disclosure, confidence explanation, and no-bet trigger guidance.

## Required Output Contract

Always return exactly **top 5 player picks** and include for each pick:

1. **Player + market** (e.g., passes or shots line)
2. **Direction**: Over or Under
3. **Confidence**: High / Medium / Low
4. **Rationale** tied to listed factors from references:
   - match context (home/away, weather, competition format)
   - player role and minutes expectation
   - market logic and implied probability checks

## Response Contract

### Assumptions Disclosure

- Explicitly list any unresolved data assumptions (for example: projected rather than confirmed lineups, missing source snapshots, weather uncertainty).
- State whether each assumption is likely to help, hurt, or be neutral to the recommended side.

### Confidence Explanation Rules

- Explain confidence with factor alignment language from the scorer output (top contributing factors + risk flags).
- Keep confidence labels constrained to `High`, `Medium`, or `Low`.
- Avoid introducing manual numeric confidence percentages or custom scales not produced by the current pipeline.

### No-Bet Trigger Rules

- Mark a pick as `NO-BET` when scorer output returns `recommendation=no-bet` or `direction=no-bet`.
- Include the related risk flags and blocking warnings that justify no-bet outcomes.
- If contradiction checks fail for a candidate, prefer `NO-BET` rather than forcing a directional pick.

## Quality Checks

- Ensure rationale cites at least one match-context factor and one player-role factor.
- Reject picks if implied probability sanity checks fail.
- Prefer transparent assumptions when data is incomplete.
