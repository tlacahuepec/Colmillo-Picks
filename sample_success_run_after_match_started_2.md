# Soccer Prop Pick Report

> **Risk Disclaimer (Mandatory):**
> This report is informational analysis only, not financial advice, and does not guarantee outcomes.
> Sports outcomes and player usage can change rapidly; always verify market availability and your own risk tolerance before placing any wager.

## 1) Match Summary
- **Fixture:** Bayern Munich vs VfB Stuttgart
- **Competition Type:** cup
- **Kickoff (UTC):** 2026-05-23T18:00:00Z
- **Fixture Status:** NS | Not Started
- **Venue:** Olympiastadion, Berlin, Germany
- **Weather:** Partly cloudy | Temp 18.0°C | Wind 10.0 kph | Precip 20%
- **Lineups:**
  - Home (projected): 4-2-3-1 — Jonas Urbig, Josip Stanišić, Dayot Upamecano, Jonathan Tah, Konrad Laimer, Joshua Kimmich, Aleksandar Pavlović, Michael Olise, Jamal Musiala, Luis Díaz, Harry Kane
  - Away (projected): 3-4-2-1 — Alexander Nübel, Josha Vagnoman, Jeff Chabot, Maximilian Mittelstädt, Pascal Stenzel, Atakan Karazor, Angelo Stiller, Chris Führich, Bilal El Khannouss, Ermedin Demirović, Deniz Undav
- **Injuries / Suspensions:**
  - Home: Manuel Neuer, Alphonso Davies, Serge Gnabry; none
  - Away: none; none
- **Standings Context:**
  - Home: 1 (89 pts, 34 GP, title_race)
  - Away: 4 (62 pts, 34 GP, champions_league_race)

## 2) Candidate Evidence Table

| Player | Team | Prop Type | Line | Passes/Shots Trend | Minutes Reliability | Tactical Fit | Notes |
|---|---|---|---:|---|---|---|---|
| Harry Kane | bayern_munich | shots | 4.0 | baseline=4.5 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions, strong_last_5_form |
| Matthijs de Ligt | bayern_munich | passes | 54.2 | baseline=60.2 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions, strong_last_5_form |
| Waldemar Anton | vfb_stuttgart | passes | 50.3 | baseline=55.9 | stable_minutes | minutes_sub_risk | away_context, blocking_warning_active, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions |
| Jamal Musiala | bayern_munich | passes | 63.5 | baseline=70.6 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions, strong_last_5_form |
| Jamal Musiala | bayern_munich | shots | 3.1 | baseline=3.5 | stable_minutes | minutes_sub_risk | blocking_warning_active, home_context, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions, strong_last_5_form |

## 3) Top 5 Recommended Picks
| Rank | Player | Team | Prop Type | O/U Direction | Outcome | Confidence Tier | Primary Risks | Why This Pick |
|---:|---|---|---|---|---|---|---|---|
| 1 | Harry Kane | bayern_munich | shots | Over | NO-BET | Medium | blocking_warning_active, home_context, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions, strong_last_5_form | minutes_sub_risk=0.9474; role_opportunity=1.0 |
| 2 | Matthijs de Ligt | bayern_munich | passes | Over | NO-BET | Medium | blocking_warning_active, home_context, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions, strong_last_5_form | minutes_sub_risk=0.9474; role_opportunity=0.88 |
| 3 | Waldemar Anton | vfb_stuttgart | passes | Over | NO-BET | Low | away_context, blocking_warning_active, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions | minutes_sub_risk=0.9474; role_opportunity=0.88 |
| 4 | Jamal Musiala | bayern_munich | passes | Over | NO-BET | Low | blocking_warning_active, home_context, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions, strong_last_5_form | minutes_sub_risk=0.9474; role_opportunity=0.62 |
| 5 | Jamal Musiala | bayern_munich | shots | Over | NO-BET | Low | blocking_warning_active, home_context, lineup_unconfirmed:Bayern Munich, lineup_unconfirmed:VfB Stuttgart, severe_guardrail_conditions, strong_last_5_form | minutes_sub_risk=0.9474; role_opportunity=0.43 |

## 4) Availability Check
| Rank | Player | Prop Type | PrizePicks | Alternative Platforms Checked | Final Availability | Retrieved At (UTC) | Fallback Applied |
|---:|---|---|---|---|---|---|---|
| 1 | Harry Kane | shots | unknown | none configured | unknown | 2026-05-23T19:32:55Z | no |
| 2 | Matthijs de Ligt | passes | unknown | none configured | unknown | 2026-05-23T19:32:55Z | no |
| 3 | Waldemar Anton | passes | unknown | none configured | unknown | 2026-05-23T19:32:55Z | no |
| 4 | Jamal Musiala | passes | unknown | none configured | unknown | 2026-05-23T19:32:55Z | no |
| 5 | Jamal Musiala | shots | unknown | none configured | unknown | 2026-05-23T19:32:55Z | no |

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
- lineup_unconfirmed:Bayern Munich
- lineup_unconfirmed:VfB Stuttgart

## Audit Log
| Model Version | Home Lineup Timestamp (UTC) | Away Lineup Timestamp (UTC) | Odds Timestamp (UTC) | Weather Timestamp (UTC) |
|---|---|---|---|---|
| soccer-prop-v1.3-context-normalized-form | 2026-05-23T19:32:50Z | 2026-05-23T19:32:50Z | 2026-05-23T19:32:53Z | 2026-05-23T19:32:53Z |


## Data Quality Notes
- Missing fields: none
- Reject prediction: false
- LLM status: failed | provider=gemini | model=none | latency_ms=2470 | fallback_used=yes

## Provider Call Status
| Provider | Final State | Deterministic Fallback Used | Error Summary |
|---|---|---|---|
| fixture | success | no | no |
| lineup | success | no | no |
| odds | success | no | no |
| weather | success | no | no |

## Sources
### Fixture
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEPwZ9DX3hN5YKBZRPuvl9bw-0kSpAM__RBSy6IBrt-05sqqr1cdUlrMmBRpjfsA3n8cDjLKx47LS_0ddfAGxphaatfkrFM5m4_LIjURm_BKDNeYt1iI6yyhlEducDOu3YY3gTw4sYi82s_LaccLxKRaM9Tj6xZsfpnERrHd6hpLaXHxa7-Dc_0ZnxQKvD1tkBlFIjmPRg=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGqUoJHHRvHGy6L8WJdXx_dtbnAuFe1H7Mmy5dgDSfiCHItpdS2PsNCE9GOCDW_m44nRWi5ITmexG6n3x3qTOV6q9GBDEtQkpzvps88bP1lA-r-PBx3fT8TeiKfZlLeov9waxdWiK_9teLLjcElsLvEHV3BlZhR4pLk-RBMEXOHjuzJnW5vQDZwMrRmUkdfzaz_Ujgf_BJ50g==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGwrwqIYpD4dWr29CXm4CUrJYK-IAS5moHuV0xESVAScIs5vAf9OoNpxoZFUO_SZoIiYPZyf8Jm5tjluNm9SEQCr4NNwkopYIk0d3s99EJdVF47efmqrUIq0ym_PzJ7ZKiHtehvMes2GurchXnWxSzcwN6YLqRNZmDE6UUuPVcvIF3S7xYVrW0NCt06iX7tveup8VOzA3WYNY6oO_wV4bnXDivdJCmrEg==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGLPptkLJZqHXdpyI1wykpoBFgOP7-ya2VhxczdWC-mKWgKl1hhrk2gKpm8p4GWk8qQjqdW3_KeCVybUeVag9SxkFx2l3FSAp_48mvonn-fRoXJ4vSSvaqH4t0Logs-axFXNUCju2V72_sjjFWN9OH4rgTzPGQV5ynBaxWh6YG1JkFKZII9VWkllkU5uGUTxS3QuXykJkWUuLifmg==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcoPg1jNx84gRE3_L5Q_iGS5IsIySRBDJLBZeithpbF8NPcFHVnnpB1ivxELblKiN5n4VTWN5hfNe2hnBzCVgMnJsv_i4b-o-tq-w2avW4cFXOH_mGyiI7etZVQMmwZiC38Nu03KlH3PaPuL95fDmTkpc5t_gUIO34Qee4GQwN0rzIfCNBMt6RYyz7bhliFbvxOdS6FeDeVtUBIueD)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFY-r3FPxy4WfiLeXG_e5MqwreiqbVyUwqPlv4DjktDQNIXuBrp0rlNBxHC5ccBiNOJ0Q5G7tdcNXdjgpHNUNTIayxNU40Ez1vpzeGMj3RuR84jLYMia-8TI4Vwo38ljevKV8zoDz68eEVnZvmM5FkKw6Bo76LqCXfBqB2m19bRc4rxVnlgRuvhdH3HsdE3Me3x9K4KYZYVD88KvgEF3nrcSw==)

### Lineup
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGaEcO7wuAauzj8wDTaD_O7xqPRZX1fSldpJvOZsT332dEtaNpwi-OuxxCLKFZUBNUrUx8qKLDiP59KGk7W-xIRPT531tifOg0dHuesqabwxunbUekhnMBmoSdCu5SEaRVoLQ3rPStf0sEhCvHku71JBbEFgZbQfcSCxKA-8A9ygYxGw5akepF-L7I3Tk5V17sqm2hGFVZPt4Bqh-69_gQbn0xN7pt6hdpz)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHTFrJRA_ybKPpdziJS5erZvOw8Wlk0Agg6OsqHlDbITgrEuiKmDgqnQV_fjsMKXpiYYKBZV9F8WH-SabQC1I8OgHFOJXfXYfUmGHzsYTDEIZJSahOyhnLJwKAdRStNUXuFT_Elg6a9VgPI5n0dQ2XoQxITDWmSyDFAdHaIu7Yxd2E1Fc78c9hsHFdmBaGVMKbzF6RJXABwpedt7kyIfYWvG3YTTXlKjQ==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHmeJzhFoTHpqP-yHI6d8FEnEooa7CiO4_ZbqXL3562Q1BWwyUDdip0OaEhh-6O2jA8KZHUMF6xfSjkd4QPZZ9aarzSW0OEs72pSGKQO7QIoa47BIEhqZciYRC6_L4hDwq1eFbhmYqF0yxtfsrsKHiJesU15_-PPhY9zWOvTHAxHY7Cw1LparBNciZb1BD9kJUbB4PXWWFC9QHAtHLfoyag6fZN9VYlS9b-jMMzgD23DvWfi9BSiw==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFMTBARNNmN0a2BUZExVaWLSRmOsmyUPawnuO5lIAPklKwrsK9O1iPgPcR8POmuKSLA2mujostiV73rStOiBZutMOF2ROK_QfgoRJJ4Xt__pjp1MwzVaYeNfiPHnCEaMbf8CRym_GSNaX2feiiyC0LIBjXxYp8Mpk2DeD0aRVgQ6qlUkZcgFow1FPJxmklcdUgyrVSzvOdGvBw64xFDOd_HwyfWVR_FzmGFPpVB8iDn4sniIiotEXeoRRbLK1pLFpLCKGhaSf7big==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHuFg563NqAYsKxFMYTn-pXS2gzH6BaeKNa4FZX4tzd96CamzP0B5b4Q1Z-3GRLSBjI8NH5ocqwkg4hG6Hp0NcT-wA3U68JeZxysoijEfh-D2GG2xEr9epKQKP8UHAYp6OloYjsj6j8m51k04iqiLMRnwf7fNwvGtxSCWuquXTZAjF_rUtOGkmaNCvGy44F_xbhluADLQ-Uc9GPbO_Lq4ZBLFmBXjX52NwndSk_q1gfSSnwxAkB9A==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHXoyAh2PYd69nJJXvhlxStKGOz6A0v4gumU-MkR-6JPqOkw5GJwBhDlVy5HwgwDx86YkLFOSGgzIBwxMH8HCeoBBMMTRPKjenIc9rHZ8bw2UecjdSG2ClHjg3KwDOPxtjEfjYL77deVLKS5080oa2v-SlIuXbqXybaCqqlKY19jjMvhwKXj2Ff9P8cxGoNoIaSdH3amrn0UenFv6wDbd6EIt7psg==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFUzKH25M73DfOWm4DXc1ixJVCJOr-RJF-bNsLWMweLCAQiena3vuekLirVCLh2dyLC54JHKtRh0DLliiyY9NLM5KFD55gRoae2n7bID4UIM1QK2MYP6ls71ELUS-piKaycDX3zIY4hqZ3Z8obGrfo2IwYBIwJSOR8TyhR3c3olUslol74Uj3fEv7_9I1KX-SgZQ0H0EpB_Eml-CKv0Bjty1rL5kS9kqihAEw==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFVkuR2xqwSkWS9wKNmozhOCUenCPdsHt8Jbg9C_GjyfWY0Y63akHlaJBUXa1oIzmjqjtTIrFEB-vT8jeZ8IVsA0tFl4CM_V79qz0k-WoR8mG1yyGNmWwOyPqiJ6yFLbUidJ0oR027BIwpJe818AklkBF-bnavA6C7saUi6T8cEqXYGMoj29o7NG0DCitjsXdBBHGG7a4BkWEjvU9mH9ypz0DcIZPUfgRQ=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHcsa1YjpsT_rSYbeSlNsFMEi0ET0fgofujKSadfPTrODPsDMq8MEnCNSIw_NTTuTeu9Ba6IyXZ4KDSu9zB4FTbVXOBT9Pxg2rSKi5FF6Q6Uk6w0oDvCqCvcOQjSx14p5Uocor6DEerCy2FamR0UVb0ZLInawdKnmlgLHF6AY01BmajwhCBQTtDH6f0IFblWXVtHWnvxvINBG_qXYvwISMcdIOSv8dg0Sk=)

### Odds
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFGvQP0HAoAEVZ1roW-trMn-X8rcQEPxkovktK1H6eyZY-yRvWUC2imN3DCW9sIZDxdlH9b_wtv1xM0UQkZLtjPVgM-Eo_EQwZ3spslGzeSNYVQpWRwtAYoOZ6AYBoLXeQvhldMi1xwqlAbLcrEkPEBdEed9lPFA6lpotWz2-L3n304TyAXqxxbC_PHMV8Hc5ywurRAy5yJHCQa5NsmCHzcsQ-qQaILxhDUEn-98mZIA4liCRBqlEtG0g5H_mWX7ID3j4jo)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQFAboKLJL4645W2Vwgvs9hPXXm6UC9EbLORpNlMq_kGTZ2Anh9rngoRDLtb100ealpB5K1_h-78kTSVigxUrHIa2AiXS1WKPI_nMZssf3m0Wsf6uMy9aZbxoLyQ3gRJ3e7ODhJQmFxVBpP8OY99tQYe7mHPvLZGEVMbfAyKfTF_j3hB1AVYn8hGN7jjX0veFCP5p45PxmJCCsjrCuYWpgsqxiB7p8fsEsmpiNdoA24ay5wLy86z5ItAT_zN6zH_tbHssZNIbGHL)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQEqSkWFamajAaxYhHTUQ5udd2vg0g1MYueoDPsMxQRx0l5RVWQUWQ5JTUWusqFSEzlnTMEfmQn0xCA17Szm9M7fNzw-Fawlnt6bjGIXUnNF6SkwRHIKyAeq3SsWCjl60KAabmk6iIM-GpbU2L6HQOJpVIGGYYXpcvoLjBJLMtQKCQYHSZobp6jbZMkTlfhnA4W6oCNqSMZrRkskx6944zv7cAUkW-mMQ6Nz7Ts3Jy5jn1ADyf2OJ8rGjuiQwA==)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQHHlUoknVqE9lKIN0j_AtjhBma3znnGBICrYVWHR-YjAY919OL7UhaOr0Q4d_GvmptNLYRFOC_8fEfr1LaH4kUxLclfs462Yjvz2GkCk1Chbk0XLs5BfIGs4CEkNvOGYIGJomHM1bFAIKPErv57QkV8PvoQFOUkjMMZd0Z5-kmy4Egk6-hS3mOWYVuB4YCNBiNDKaQQmzv5RpZroTcozD8rlPGXBInodU4lvra4mB37DdN0EhCTjFw88L1WpgLQxySzZZw=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQG_xPt0RizLesFXFF9d7BHN7pkquwnSr65ZwILInLFa3b26X-e8ghy1LsOlbh1iE5pQpGqqRg5VocHH71KH4VWI6GAa-dd-Qah9m-ppLuPORqs6eEyawi_4FdYh1Lsg-yQftpI8_CJxTQM_RLT1JLNe9ozcg-EauTNw2GsHZ6gcNGcyP-afD69vUuwXAl9osO48HtCF-MaBDlNak9NwPksEG3DfIw9Di7eU7kHMp5Xvt9jlMH69yk6RKEkd1wq5RYVneFE=)
- [vertexaisearch.cloud.google.com](https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQGj046u7fZQ-6JAh3tJVSpG2KIRBWzqZxZNpCE5LLLmiBdzFlLmXJ8xbGezpoxyLHngOWJWfESF-f_-0IW_ffpqKGXZUVupW-ei-mOp7XnE6CafD31SsaXcsqqTXuyq98-A9ZXgeausxyVXXv9TmbEwEtCTqK4s_DAY20Ey399etSQ6UaFJQFmKpciRJgIyBtqp-JswYnowxMntvIAFSLT5DXpKwNucguxWEKnV1425XHUL9V06FKQbrD5ff2YteE4vnDLucg==)