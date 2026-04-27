# Soccer Prop Pick Report

## 1) Match Summary
- **Fixture:** {{home_team}} vs {{away_team}}
- **Competition Type:** {{competition_type}}
- **Kickoff (UTC):** {{kickoff_utc}}
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
| Player | Team | Prop Type | Line | Passes/Shots Trend | Minutes Reliability | Tactical Fit | Notes |
|---|---|---|---:|---|---|---|---|
{{candidate_evidence_rows}}

## 3) Top 5 Recommended Picks
| Rank | Player | Team | Prop Type | O/U Direction | Confidence Tier | Primary Risks | Why This Pick |
|---:|---|---|---|---|---|---|---|
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

## Data Quality Notes
- Missing fields: {{critical_missing_fields}}
- Reject prediction: {{should_reject_prediction}}
