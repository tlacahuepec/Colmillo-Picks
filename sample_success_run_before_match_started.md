# Soccer Prop Pick Report

> **Risk Disclaimer (Mandatory):**
> This report is informational analysis only, not financial advice, and does not guarantee outcomes.
> Sports outcomes and player usage can change rapidly; always verify market availability and your own risk tolerance before placing any wager.

## 1) Match Summary
- **Fixture:** Bologna vs Inter Milan
- **Competition Type:** league
- **Kickoff (UTC):** 2026-05-23T16:00:00Z
- **Fixture Status:** NS | Not Started
- **Venue:** Stadio Renato Dall'Ara, Bologna, Italy
- **Weather:** Partly cloudy | Temp 18.0°C | Wind 10.0 kph | Precip 20%
- **Lineups:**
  - Home (projected): 4-2-3-1 — Lukasz Skorupski, Joao Mario, Jhon Lucumi, Torbjoern Lysaker Heggem, Juan Miranda, Remo Freuler, Nikola Moro, Federico Bernardeschi, Lewis Ferguson, Jonathan Rowe, Santiago Castro
  - Away (projected): 3-5-2 — Josep Martinez, Yann Aurel Bisseck, Francesco Acerbi, Alessandro Bastoni, Luis Henrique, Andy Diouf, Petar Sucic, Henrikh Mkhitaryan, Matteo Cocchi, Francesco Pio Esposito, Lautaro Martinez
- **Injuries / Suspensions:**
  - Home: Riccardo Orsolini, Martin Vitik, Nicolo Casale, Nicolo Cambiaghi; none
  - Away: Hakan Calhanoglu; none
- **Standings Context:**
  - Home: 8 (55 pts, 37 GP, europe_race)
  - Away: 1 (86 pts, 37 GP, title_race)

## 2) Candidate Evidence Table

| Player | Team | Prop Type | Line | Passes/Shots Trend | Minutes Reliability | Tactical Fit | Notes |
|---|---|---|---:|---|---|---|---|
| Lautaro Martinez | inter | shots | 2.7 | baseline=3.0 | stable_minutes | minutes_sub_risk | away_context, blocking_warning_active, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions |
| Alessandro Bastoni | inter | passes | 63.0 | baseline=70.0 | stable_minutes | minutes_sub_risk | away_context, blocking_warning_active, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions |
| Lewis Ferguson | bologna | passes | 40.5 | baseline=45.0 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions |
| Jhon Lucumi | bologna | passes | 49.5 | baseline=55.0 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions |
| Santiago Castro | bologna | shots | 2.2 | baseline=2.5 | stable_minutes | role_opportunity | blocking_warning_active, home_context, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions |

## 3) Top 5 Recommended Picks
| Rank | Player | Team | Prop Type | O/U Direction | Outcome | Confidence Tier | Primary Risks | Why This Pick |
|---:|---|---|---|---|---|---|---|---|
| 1 | Lautaro Martinez | inter | shots | Over | NO-BET | Medium | away_context, blocking_warning_active, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=0.95 |
| 2 | Alessandro Bastoni | inter | passes | Over | NO-BET | Low | away_context, blocking_warning_active, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=0.88 |
| 3 | Lewis Ferguson | bologna | passes | Over | NO-BET | Low | blocking_warning_active, home_context, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=1.0 |
| 4 | Jhon Lucumi | bologna | passes | Over | NO-BET | Low | blocking_warning_active, home_context, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=0.88 |
| 5 | Santiago Castro | bologna | shots | Over | NO-BET | Low | blocking_warning_active, home_context, lineup_unconfirmed:Bologna, lineup_unconfirmed:Inter Milan, severe_guardrail_conditions | role_opportunity=1.0; minutes_sub_risk=0.6158 |

## 4) Availability Check
| Rank | Player | Prop Type | PrizePicks | Alternative Platforms Checked | Final Availability | Retrieved At (UTC) | Fallback Applied |
|---:|---|---|---|---|---|---|---|
| 1 | Lautaro Martinez | shots | unknown | none configured | unknown | 2026-05-23T15:44:46Z | no |
| 2 | Alessandro Bastoni | passes | unknown | none configured | unknown | 2026-05-23T15:44:46Z | no |
| 3 | Lewis Ferguson | passes | unknown | none configured | unknown | 2026-05-23T15:44:46Z | no |
| 4 | Jhon Lucumi | passes | unknown | none configured | unknown | 2026-05-23T15:44:46Z | no |
| 5 | Santiago Castro | shots | unknown | none configured | unknown | 2026-05-23T15:44:46Z | no |

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
- lineup_unconfirmed:Bologna
- lineup_unconfirmed:Inter Milan

## Audit Log
| Model Version | Home Lineup Timestamp (UTC) | Away Lineup Timestamp (UTC) | Odds Timestamp (UTC) | Weather Timestamp (UTC) |
|---|---|---|---|---|
| soccer-prop-v1.3-context-normalized-form | 2026-05-23T15:44:35Z | 2026-05-23T15:44:35Z | 2026-05-23T15:44:38Z | 2026-05-23T15:44:38Z |


## Data Quality Notes
- Missing fields: none
- Reject prediction: false
- LLM status: failed | provider=gemini | model=none | latency_ms=7428 | fallback_used=yes

## Provider Call Status
| Provider | Final State | Deterministic Fallback Used | Error Summary |
|---|---|---|---|
| fixture | success | no | no |
| lineup | success | no | no |
| odds | success | no | no |
| weather | success | no | no |

## Sources
### Fixture
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGbp1OIpr84rskTiiQ9-A6TUNyJXE5W-QXEhcR8s-lGS-b7IULKEsiH9aVNsnP5iuFXn5wXvnQj-6uL0vXW8G3hrj9spBnA45_5DYK2sQLAM3JZtfvXQDeWnlig-Tbg0AwIKiqorbvZTHBYwHEU40DJehsYuMheisiaNLywOMPiu-Wa2RHjeUs99Dbwa5CP68MDrBieENT6CaizHIOM)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGZsrD5qNG6kPNyQKjHuwvFVcHlkiv7KVe2T_kUCpho6kDEj0xl2jmqku0s-12PmNwvs-Ue5RUr8DvWxU1qBva2e2NeDwCXS_IsBX6rdhCYUq24pCFJwerQag1kSKIde25Pxd4hkvWFRLBfax_J8HptZAjqq5U2Kwt55gtdrIs3y8jMraHregGUqPkwFPgnBF5mGeUvjjgWxPTRNcMy1lnTS0QvZMgW-7FO9gSu47A-GyM=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEQNJmzuizKcI0BRQMWJlP2MvlpcPZtJvVntBt0R44QmookxY5ZhthJ1bIGRsS3654U1vgq52Zxbd7mtc0eR1kVWG9Z2ZPMzlJIUoYikr-xRW94VEC4JE9cHHOjrXBlYpigdGqQE-EJzYd7AAoR1t4GKSIupAlDkf48_Y3aK50QW5JqdIoZ5bqojgBjZumlKPdb8PiCVWaVOzBajbzIEw==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEddy_2KLqIEn0hT1u1TU21LwlP-jSYEly6En4D3qGOwmRCL3G4Yc8QeV0idI9NU4hfWyeOXgodGggS5LB-fvR2rzUxK0WLjJPfSZddGFAIB3jzbg0q5Gqk0Kvyd5TTGlh97uD71o8Q_yWmjwUDBzM0bzk5m0DF9xDmrNoMM-UQvcXMjRxxn2dVTNeyohGBOQwj_5Z8t6euZBE=)

### Lineup
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHwzgOO9ZNaLXpCF7-tp6jAzmSz4v0ZD3z28YPl5xXLmwFkwQtDqlEUJ3EYJVpuk4z3OLluGNZaj6l-T4Nxmgg1m6PqEsRl1LNFun809zMIOuYOFJYGgmnYbEzRVbTJIyYQL_PffF424KVEl5KJA8xzZ9XxB3N_86BCBY7ALsU8juM3L3mq5FKPvCTfUzMUlZyHAt3g2KU6383QySbDFBdj_GA=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHOUCFNVDvz1-Z75lCp9z7rMVjp33OHPCBo8ytBBipzENWfFXQp7Rcv0CUEf-PCY5sarp11rBkJuptKsqyaOdMr3D3Dq53OFF6Hld1ScbopowP5RJM4PV0KSB_ocrH4Gxf-QxqrebTjuceax7ht0OaaKztkur_2dhPUTOXaegE6Pv89eqUHhYC5wnHayvBIxbGu-ffs4DV8kEN2w7yId8Ak25YJFHLF1qKSxfpokw==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGAV5U26vQydU01uQdhmj7DbaqB7jVE2ZbFycO4VD8bbDujH99r-PuVVJP-d3i58qsbVWR4Ce0ucrQ_QVkom3kMOQz94MrgBOPAk4E5Etk-Be8beD7zkiI9hybgar8SqeSlgHTbcdFclwRXgYL4PBvmB5SP9iBnhz3rk69sVNx0QIA6v0Fz81aaG6_WVVOVDci5dj0pTiCtKDR_DfGogXXu7nDQg5Ddge3K-j9hf7elZmMEnpbkZA==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFFIjWHQ8deiOpDlfF96wR6oBuU2lWlBiS0lUXyevd1ph0NUmSohzWAuN34_H8REmhOzs7xQ1B88Q1rmwWEjL8qZjXpT1BmXfy0WfkQMP5CvPYsgPbg2QiAIjXsmTZOohNXdLcdvsvARgYWD52BeU1joPKuWxpnxqZJP7Rk5Ar8UXHlNSEUGlRZ1gQTRpcnAcKF_glh-cdLcYdB27o6OUNEo3J80tQMybyyTjyyvgr-hIE=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFsl3O5nChmlxlgp3ZPvTvXoc4IIFs9QR5WjVCaQlLcNjbjwoiNE3pOHRqTcXc5Gcig-nJw11I0rahTQXgeRcESYpoI0DwaLE2IMq9_O82D1CSg6R3KvC3H68zNemnOdDUxIe9tyf2Evuj0E8H9odnehgBAvA8cxEN2fJqOWTWSZUgbskBp9e9u31UCyh6Eh95SydhUZv9h4m-co17e1A==)

### Odds
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF3vWBktr0cAIYCg53CYazlBl9dGTnQ0uXeSrSOqx2XRFgY_3pjm6xR8NH95dT6P0dfWXBl_Nidj4Hf3sNdQFSd72AoW9ldP0rFxnYYHqEIZLXTf1gaqB2OzK6M43reTYs0LWawXbV_dpHpPIXx86Z3KwtZomDCZzHPkrocg-HPotzabocx6XEB77Dm50OAdSzFap7pdQdRPeyG9blUe7oN9SDZ2LE=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQE3JzRFDRoReTVnmRQrHBTgGAvpBdgIB53A4K0tpPyAqtn0vowl4YmUgUBaSitLmYAQZsAxB3b4h3uQadjlGSiYrHanI6hi8_b6DD4yslKuW8WlTjYeJQpE19YXS0zP_VxsSppxBEUgHG0YejjGxNG_eM0aiiE36l9ixXKtQ-czKcqUs7vqkpXnfnbbmRJ4By7R-6JH1qVYepzjKS37gLKzSKBIF7Y=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH2ykViKHf9EdmOOWhXpKfJMYb2p6acTjSslCAR5hjnYhjPLzP_VEXAoI3maDknFa1nar_HaSG7QUad7BNDdIeZumWAHoWd7K2eBFwCiXCG1KP5KFF60YVoTkZIvv1uU5WaaoA53x42SraB8gCFeagchMGG3UGhssfPqnR-p-z3kb0Qx-ac3Gzil-sdZmhuX44PFnyZ6B4M3j-r4Nt9gElyJrHKG3bvpUs8INYKO7oWjY8=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHoIoCi7qairw_52-ji0X6DI9uCbLTcE-4qwCpvTm5SzO9jCOr6sc2pRr6D-RuZdjxfUsMENpfbciFijEJrLIjhvp9obu2P6lsA0XSe7IRDDEfkJE6zsDP9GKEW2gPcT3ThGHgyp62E_kHfDhcR_wX6ANbnD4O47g2UI_WwGG3fK2aqNHUixBcJjdWnPjerDix0UHYhCu8qcwxSLtf5u-963gful-5jZPTe)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEWM0KMUMahWHw8reNPZnS2Rcu5gFtTnfbhc-hQWL6nSwxJID8NUlk3CPdYRAfyp8Rk4In0PGgFuRwKDadK7UbLjED6Dp67TdEKN9rnrRM5wZquS70cgzsqsR68ExjvfmKeMrBb3MlHD7raF1SNYsPUrXs4xVB3MOafSC3NsrEIe-1TTxjX2qcP04c8L5FwFM_1aUE28pqmiCPQowdYjGV2f3XSDKUqBQ==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGz28hHrc2Q1R8poEAL2zcGPQ7AolC-a6SakN8QMg_jQKN9ef1ScoIBMZsu2Hm649R5TEiSQPNz1dOjnzISwsHWyrUD9b4eYKPvqwsmvYI5Dq91ISZV_grzhy2d1MBxU3pXKlQbdipXDDBqGbUyxNBkdFsWoRwkYHaonU3HZvI8j81Ln9qpZ8XvrUBYg7xuffCQWLaPlupENfF0Q4y_C-zd6BfYbfsM)
