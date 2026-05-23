# Soccer Prop Pick Report

> **Risk Disclaimer (Mandatory):**
> This report is informational analysis only, not financial advice, and does not guarantee outcomes.
> Sports outcomes and player usage can change rapidly; always verify market availability and your own risk tolerance before placing any wager.

## 1) Match Summary
- **Fixture:** {{home_team}} vs {{away_team}}
- **Competition Type:** {{competition_type}}
- **Kickoff (UTC):** {{kickoff_utc}}
- **Fixture Status:** {{fixture_status}}
- **Venue:** {{venue_name}}, {{venue_city}}, {{venue_country}}
- **Weather:** {{weather_summary}} | Temp {{temperature_c}}°C | Wind {{wind_kph}} kph | Precip {{precipitation_probability}}
- **Lineups:**
  - Home ({{home_lineup_status}}): {{home_formation}} — {{home_starters}}
  - Away ({{away_lineup_status}}): {{away_formation}} — {{away_starters}}
- **Injuries / Suspensions:**
  - Home: {{home_injuries_suspensions}}
  - Away: {{away_injuries_suspensions}}
- **Standings Context:**
  - Home: {{home_table_position}} ({{home_points}} pts, {{home_games_played}} GP, {{home_motivation_tag}})
  - Away: {{away_table_position}} ({{away_points}} pts, {{away_games_played}} GP, {{away_motivation_tag}})

## 2) Candidate Evidence Table
{{rejected_prediction_banner}}
| Player | Team | Prop Type | Line | Passes/Shots Trend | Minutes Reliability | Tactical Fit | Notes |
|---|---|---|---:|---|---|---|---|
{{candidate_evidence_rows}}

## 3) Top 5 Recommended Picks
| Rank | Player | Team | Prop Type | O/U Direction | Outcome | Confidence Tier | Primary Risks | Why This Pick |
|---:|---|---|---|---|---|---|---|---|
{{top_5_pick_rows}}

## 4) Availability Check
| Rank | Player | Prop Type | PrizePicks | Alternative Platforms Checked | Final Availability | Retrieved At (UTC) | Fallback Applied |
|---:|---|---|---|---|---|---|---|
{{availability_rows}}

### Availability Fallback Behavior
When platform availability data cannot be fetched:
1. Set **PrizePicks** to `unknown`.
2. Check configured alternatives in order; if none can be queried, set each to `unknown`.
3. Set **Final Availability** to:
   - `available` if any verified source confirms listing.
   - `unavailable` if all verified sources explicitly deny listing.
   - `unknown` if data retrieval fails or sources conflict.
4. Record the retrieval attempt timestamp in UTC and include the blocking error in notes.

## 5) Decision Playbook Checkpoints
- **Lineups / Injuries / Suspensions:** Confirm both teams and note any unresolved assumptions.
- **Form + Standings + Home/Away:** Ensure game-state rationale aligns with venue and motivation context.
- **Weather Impact:** Confirm adverse-weather signals are reflected only when present in model flags.
- **Market Agreement Sanity:** Verify market agreement flags before finalizing confidence or no-bet.

## 6) Response Contract
### Assumptions Disclosure
- List unresolved assumptions that could materially affect the pick direction.
- Mark each assumption as likely positive, negative, or neutral for the recommended side.

### Confidence Explanation Rules
- Explain confidence using scorer-produced factors and risk flags.
- Keep confidence tiers to High/Medium/Low only.
- Avoid manual numeric confidence scales in narrative text.

### No-Bet Trigger Rules
- Use `NO-BET` when scorer outcome status is `no-bet` (direction can still be over/under).
- Include blocking warnings and risk flags behind no-bet outcomes.
- Prefer no-bet when key checkpoints are contradictory or unverifiable.

## Guardrail Status
Blocking warnings:
{{guardrail_blocking_warnings}}

## Audit Log
| Model Version | Home Lineup Timestamp (UTC) | Away Lineup Timestamp (UTC) | Odds Timestamp (UTC) | Weather Timestamp (UTC) |
|---|---|---|---|---|
{{audit_log_rows}}

## Data Quality Notes
- Missing fields: {{critical_missing_fields}}
- Reject prediction: {{should_reject_prediction}}
- LLM status: {{llm_status_line}}

## Provider Call Status
| Provider | Final State | Deterministic Fallback Used | Error Summary |
|---|---|---|---|
{{provider_call_status_rows}}

## Sources
{{sources_section}}
