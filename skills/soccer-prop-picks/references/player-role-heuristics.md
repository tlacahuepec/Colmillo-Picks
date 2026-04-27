# Player Role Heuristics

Apply these heuristics when evaluating player props:

- **Captains and leadership roles**
  - Captains are more likely to retain full-match minutes in competitive fixtures.
  - Leadership status can stabilize baseline pass volume for central organizers.

- **Likely 90-minute players**
  - Prioritize center-backs, holding midfielders, elite keepers of possession systems, and world-class strikers with secure roles.
  - Validate minutes probability with each player's last 5 matches (starts, substitution minute, and workload signals).
  - Downgrade players with recurring substitution patterns or workload management risk.

- **Lone striker logic**
  - Lone strikers may have volatile shot volume dependent on service quality.
  - Against low blocks, lone strikers may still accumulate shots via central box occupancy.
  - If one striker projects high shots/shots on target volume, consider correlated upside for the opposing goalkeeper saves market.

- **Substitution risk framework**
  - Flag wide forwards and attack-minded fullbacks as elevated sub-risk in high-tempo matches.
  - Reduce confidence if projected minutes are below 75 unless line value is exceptional.
