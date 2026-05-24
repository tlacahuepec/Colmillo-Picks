# Soccer Prop Pick Report

> **Risk Disclaimer (Mandatory):**
> This report is informational analysis only, not financial advice, and does not guarantee outcomes.
> Sports outcomes and player usage can change rapidly; always verify market availability and your own risk tolerance before placing any wager.

## 1) Match Summary
- **Fixture:** Hull City vs Middlesbrough
- **Competition Type:** cup
- **Kickoff (UTC):** 2026-05-23T14:30:00Z
- **Fixture Status:** NS | Not Started
- **Venue:** Wembley Stadium, London, England
- **Weather:** Partly cloudy | Temp 18.0°C | Wind 10.0 kph | Precip 20%
- **Lineups:**
  - Home (projected): 3-4-2-1 — Ivor Pandur, Lewie Coyle, John Egan, Charlie Hughes, Semi Ajayi, Ryan Giles, Regan Slater, Matt Crooks, Mohamed Belloumi, Liam Millar, Oliver McBurnie
  - Away (projected): 3-4-2-1 — Seny Dieng, Luke Ayling, Dael Fry, Adilson Malanda, Callum Brittain, Aidan Morris, Hayden Hackney, Riley McGree, Morgan Whittaker, Alex Gilbert, David Strelec
- **Injuries / Suspensions:**
  - Home: Kyle Joseph, Eliot Matazo, Toby Collyer, Cody Drameh, Akin Famewo; none
  - Away: Darragh Lenihan, Tommy Conway, Alex Bangura, Leo Castledine, R. McGree, Jeremy Sarmiento, Kaly Sene; none
- **Standings Context:**
  - Home: 6 (73 pts, 46 GP, promotion_race)
  - Away: 5 (80 pts, 46 GP, promotion_race)

## 2) Candidate Evidence Table

| Player | Team | Prop Type | Line | Passes/Shots Trend | Minutes Reliability | Tactical Fit | Notes |
|---|---|---|---:|---|---|---|---|
| Oliver McBurnie | hull | shots | 2.2 | baseline=2.5 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement, severe_guardrail_conditions |
| Regan Slater | hull | passes | 22.5 | baseline=25.0 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement, severe_guardrail_conditions |
| Charlie Hughes | hull | passes | 22.5 | baseline=25.0 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement, severe_guardrail_conditions |
| Dael Fry | middlesbrough | passes | 22.5 | baseline=25.0 | stable_minutes | minutes_sub_risk | away_context, blocking_warning_active, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement, severe_guardrail_conditions |
| David Strelec | middlesbrough | shots | 0.9 | baseline=1.0 | stable_minutes | role_opportunity | away_context, blocking_warning_active, insufficient_projection_edge, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement |

## 3) Top 5 Recommended Picks
| Rank | Player | Team | Prop Type | O/U Direction | Outcome | Confidence Tier | Primary Risks | Why This Pick |
|---:|---|---|---|---|---|---|---|---|
| 1 | Oliver McBurnie | hull | shots | Over | NO-BET | Medium | blocking_warning_active, home_context, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=1.0 |
| 2 | Regan Slater | hull | passes | Over | NO-BET | Low | blocking_warning_active, home_context, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=1.0 |
| 3 | Charlie Hughes | hull | passes | Over | NO-BET | Low | blocking_warning_active, home_context, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=0.88 |
| 4 | Dael Fry | middlesbrough | passes | Over | NO-BET | Low | away_context, blocking_warning_active, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=0.88 |
| 5 | David Strelec | middlesbrough | shots | Over | NO-BET | Low | away_context, blocking_warning_active, insufficient_projection_edge, lineup_unconfirmed:Hull City, lineup_unconfirmed:Middlesbrough, market_disagreement | role_opportunity=1.0; minutes_sub_risk=0.5747 |

## 4) Availability Check
| Rank | Player | Prop Type | PrizePicks | Alternative Platforms Checked | Final Availability | Retrieved At (UTC) | Fallback Applied |
|---:|---|---|---|---|---|---|---|
| 1 | Oliver McBurnie | shots | unknown | none configured | unknown | 2026-05-23T14:32:16Z | no |
| 2 | Regan Slater | passes | unknown | none configured | unknown | 2026-05-23T14:32:16Z | no |
| 3 | Charlie Hughes | passes | unknown | none configured | unknown | 2026-05-23T14:32:16Z | no |
| 4 | Dael Fry | passes | unknown | none configured | unknown | 2026-05-23T14:32:16Z | no |
| 5 | David Strelec | shots | unknown | none configured | unknown | 2026-05-23T14:32:16Z | no |

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
- lineup_unconfirmed:Hull City
- lineup_unconfirmed:Middlesbrough

## Audit Log
| Model Version | Home Lineup Timestamp (UTC) | Away Lineup Timestamp (UTC) | Odds Timestamp (UTC) | Weather Timestamp (UTC) |
|---|---|---|---|---|
| soccer-prop-v1.3-context-normalized-form | 2026-05-23T14:31:55Z | 2026-05-23T14:31:55Z | 2026-05-23T14:32:06Z | 2026-05-23T14:32:06Z |


## Data Quality Notes
- Missing fields: none
- Reject prediction: false
- LLM status: failed | provider=gemini | model=none | latency_ms=9416 | fallback_used=yes

## Provider Call Status
| Provider | Final State | Deterministic Fallback Used | Error Summary |
|---|---|---|---|
| fixture | success | no | no |
| lineup | success | no | no |
| odds | success | no | no |
| weather | success | no | no |

## Sources
### Fixture
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGL_b8FuBKoG7xJN9etW3Z2hdH6jU1N5K0FSk5mX9btqbdfzN02WXJpR1B9vgeC34m0mQafFfnw3Z5OnPcC2MVA10z2R8Djh1CewQXOHMc0q6GUtFmbLapRnPA7EIaQkHhBVl-U2j9J6L4X790y376IqBURYRMbro5vz2B8-B5IQB96heuiHGjdQBTHEZwy8QUEwVCWSK6Z8cQr2GlyapBB8cY=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQH8vQHvlEft5kG3glue0ChS64aJz-QqOsfDNep8LjWiIPY_H1qKGT5KecNRYiM2nB40gImzPrsfK8tfsuhQhURUr1ER7zTEIyJ_Wcp6VxXZWaEJRMhLH4V12MHeTzRF9eI_g8EzmW0DzmGHs3tuxoJTWlCKoSNT7ex5QdvnACvhEqSrhBZ4QApa3_oTlwLjCa0tdJOXAhHpaMkiSDnidi0EiBIlq_0IufFFm5gKKKBwV-caM9M3dQ==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqHLY8GDzTD2zHeISuF2FDCGIdwO0BuN-UD1CAXm5GAubJ_LGDNzPktC4HLazM6hG9pmoTkQ1z1F6zCqDZ0vhbXJGVcwNu9TG672eaaB7eUbtr3xrKpOo5QDQqnZrot4Z95FdtCF2uen5OayLznn7aX97PiQP3Zg_H9RKa3h9rfRO_-SDjv6lkQyQLhz1lycao424XS4yekH9T5hToRd-l09A2arB8mA==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGHs-GIn1b7FYuxdEXUQxfVgE2GHvJL9HzSuBrgShBJB1B2W_mXtyka8AuH62NWob4Bh8XN8m2g2le6wunM5BgLsYY_l7XB8ByM5ukdoVelPYF7XyXJK_Vttk3lLUMEK6rbxdDHpzmBUEOkBFY8zJdwnymxz8lkZvTnaUlLgjKAgrxc1jReAqJSm3OA38-oC9bUkU7ZehSX3UrsXtu1H4QKkd3PEc2ReIWfZfTMCg==)

### Lineup
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGg-oRcU45hZcM-Gu-jyRClbVEQR0M5EhfcXdWxoH9QaG_qYdN18f4vD_g2Q7Sa_5OnL4QHKqUpEo9OfiHEgAVmMwMwa0xqoQBKxMS2Kso6Fc2QA65pQYdKAuJKvJ-1QqIXs8lfNPZWhVPf5z96XOy9upepsC6t4SkmBvAp2_k21lsVt8Lii8_K13mgxh3fQdVXuavahdiaAMyi04NvSmQ3z0kZpuBQa4ZY7A==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEgNmmfj-3fjbYbEU5bOCxaxA3uNWwqfTlQ4sdohCOV1XVGGagmbF7qxAV6AQwpzDZifADMth2OUMOsCfkxYDGCbz_smOPx_MptWERsxWSRmcfMJNkZxQ-_BcsYaVb7sMBuhsZ1A-tsJvDLe7WWmSuQ_WBbOEhg9mJVRGCl4t8k2uvVTM5h6CQbpLZA_5rgdR5o_kbYrrPLP741WUILhurY9J_vFOkk)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEdS5itSghfyIgg6csr4GgLhqOcgpsU1ETcIG_X4phkGKx_6Yjo3QqSGuWez0zo_kggypBa7PR-DjO90Pd2LX1MxtwJXlFd9PSybn1JNixQFzXetZ_iB3kxAmH6BzpOSLWvhmmZF3u6EvloxrnKv5mkOFMeDd5kL_jDAyJwR2mvTPcIuoBTZLSKc--_C504c3puDptlRq_Oq24mBdoh63AguSpzuvTv6cjYt4mXNVaDcsLHs0eSO3SJVdCMuObZfM6jP0T5et4JsoRNam3iYZEZBITqCJs6St6nBA==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHV6dTVqOh3D4LCN_MtxTpe4uy_es_j_q9H2eE54jct0AA8kuaFShoAlBGu-Q9vK61xL6x2pt925SbP63DUG21FP_wA-bk9xG3s6VP3uUJbJFdwkR4QBwYLDRK_JvtOaHJl5w6N0KVWY-tm6g5O9CUJvu7xhwVYkmTjC-ClXWnKVza8rJqhWGe7cA7ARtrTYpT9FD3MYeHL8YJVjEqWV-I2jIXFMdag-ElsIjf59JB9mRxekCxga7XTwVBQH9znSPZyLArol_CIq1-OYUCMGiyb2HwdNQtQplwiHQ==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHS79cCVUwGxCC3RSp6uarzAxY7gkhS-S5JMej36wraIQonCmqlM3Gf1SMVev9a53J8PCzNCzpPwmJ9LVkE-O5ZsQexSjIQQRiSUpoSwYE9XasBO77XVzVyOAYwS432XDWzed3cNsU-Eyt33Vxx0BBtxiOgWFhhfMJVvuxVLig1nvBituGiEC3zVMAiq_yy3bMDJcfpES4z1aAKNYUlj83oB4cV6FzJ_w==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEq7V13xA5sGO-nku6x8vJuHCasZjZHfJJqQYUm2L_BApFfuwjDwC74rDCfvL_-xF5fDhUzfXtm3K4zAmf7zM9fZzZQdn7_Y0bgidJfUIBNXgpQinp3jN9N48HzsVr58HjQUict4HjYKG5vyvRJfJ4hcuh0ELtD27i5POnpfI2nJC3_ESJ216uGZ_vfxjuiTDvFFWbC0cqzle3MVer3uuhD3ptJ)

### Odds
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqoSTuFLxPiwGEh4dIPQRT34ppEyPHurAKvvp8IZNzEsX574oh7MGyVSUQqtUeIh-XLEaCdJagPI83_bbANCUQGyq3dNa2TlISLpQpvx_Bmb7deY9DNA-adhWgHtMimma6klLYHbtQJhydnMqA6hc3oE9L0r7F6ssrATeE-EYtHIiqQXLbbehlhaST_HELLrxAE05yJQAEqiWvJBYS6nmJDdEf_j_Nfw3Y)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQF9c5nAfslbpR4PKZ3Tn5vbX8Yn9JYJj12o4V5OIE8BwfNULEec7E4acPDsT6Igp4Djo4AH_Y1OdEq6u09j7Vz3njNHpA7-w0M3OgT3_1dVIZC9Gwvq1MPUWUp4jGZq-TJXonAxkWnndRRS_nuyJZtbZ8LvkaFzD_S_T--kpnyQSR8Ys1h8phSPnXqTnZQ5fi1Pr2KsIowG0uVIKo4_qAoJtZQch2uaR2fRNRXRrA==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFqdzwtcXRWRIknZkWrzDYrNzeevXFArqUq-uqYTuxD9ycbf6AG04r4Bk41aVkw8ptc4kGhAFAZY56i4Xv_MYuToINfJZDyojsW1aTf6aoFlLmNOOWcPPN0PECEkN_nofGvG_SKTjhjrWuODqGFdb8-tf0600BLUHDqN85NCX5TTDLgg4PwMBvchGzkPSOI3cqpSRQMFl0vD0_KKbfwIjd5tHTmWDpKkTXLrT1emwJ0n8p07vmbJ_kSzftGznPm4FiakTFFe1Z5LA==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHJWB3U9LjsaiCFCoQb6HnrldrhMwNuAzz1JEQsP_n1AX8-dThlSepZeU1407lmsDXT7i60XQDChlgje9UjRUZ8aNHTY27YlsvZHwDSCBK-bqBHMPK76xMJcG0Jt1S0l01VwLCklTgnY2BuPJuToH1qgLqWQn5rm6TlkQoxG39-ahFDVuvVHhcdhSANgickOnAGHW6m1oqp1WIPsPUbgX2tg3UJn8DJhHE5)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFOEu_ISLm-GsbMN0QivQHC6WKklGr2ZqrDyEl1XTu_cKzskWpWfcnaHVno5DblnsOH15aoD7BannNP3abhdVuid4EycxN4JAqWqnh9r8pzsi3_JM9D-VsIi2DdDZ9kKTi3SMTSr-0pSJue0FtrVPANyDIGzAgD4oQ2h051GklAUZy3BmL_4IC80zQXCp2T_hv8BxjFpAjK0f1d1Y2kmdenU-T7GNC-jzlemPE=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGJuDlaxcyJmbmzYGMcFD3RF-tHnmvf9UjXBgsk9otnUl7fLO2hx7eqdvIJmWM8UwacZMgB_psvCmF5VlFpISEu-Pth3Zgv9WKhEvloqROD1NGghjKGrrNKcwT-7RXQnfneENl0T3GRpBKfHJUPShT2ttYZ7hSTX5GUN0H1ERBg8F8YmjKZN0_p7EJa1SdUihVlpvvac7N4SW8R-zo03bFDQFtcUbZaj-JS8A==)
