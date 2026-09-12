# Backlog triage — 2026-09-12

This record explains the board decisions made after the catalog and NFL work
landed in `dev`.

## Closed as delivered

- #207 — Best Today epic; its child stories are merged.
- #252 — LangGraph enrichment pilot; the feature-toggle path is merged.
- #264 — Top-N defaults and timing visibility are present.
- #273 — Grounding-quality metrics are implemented and used.
- #304 — International-fixture fixes shipped in PRs #305 and #306.

## Discarded

- #208 and #214 — Discord pick signals, promo/taco detection, and runtime
  ingestion are outside the product boundary. Provider and catalog evidence
  remain authoritative; no Discord successor backlog is intended.

## Deferred

- #240 — date-input UX.
- #250 — MLB reliability audit.
- #251 — additional-sport evaluation.

These remain open, but market and source research takes priority.

## Compliance follow-ups

The broad audit #226 was replaced with focused issues: #334 (Pyright), #335
(Ruff configuration), #336 (dependency updates), and #337 (repository
governance). Historical branch deletion is not authorized by this triage.

## Active research order

1. #249 — delivered in `market-source-research.md`; it defines the
   stats-first, LLM-second boundary and a procurement gate.
2. #248 — remains active. It needs an authorized, dated platform market export
   before its PrizePicks-inventory acceptance can be completed; the cross-source
   gap analysis and implementation priorities are in `market-expansion-backlog.md`.
