# Requirements Checklist: NBA Props Sheets Export

**Purpose**: Validate that requirements for NBA props backfill + Sheets export are complete, clear, consistent, measurable, and review-ready.
**Created**: 2026-02-28
**Feature**: `/Users/bb.jr/sports-data-platform/conductor/tracks/nba_props_backfill_20260224/spec.md`

**Note**: This checklist validates requirement quality ("unit tests for English"), not implementation behavior.

## Requirement Completeness

- [ ] CHK001 Are required output artifacts explicitly defined for each phase (database backfill, Qdrant embeddings, Sheets tabs, runner outputs)? [Completeness, Spec §Scope 1-3]
- [ ] CHK002 Are data retention/time-window requirements specified beyond "last 2-3 seasons" (exact start/end season boundaries)? [Clarity, Gap, Spec §Scope 1]
- [ ] CHK003 Are required fields for `player_game_logs` defined (data types, nullability, uniqueness, source-of-truth columns)? [Completeness, Gap, Spec §Scope 1]
- [ ] CHK004 Are required fields for the Props export row schema explicitly documented (including edge, confidence, RAG context payload shape)? [Completeness, Gap, Spec §Scope 3]

## Requirement Clarity

- [ ] CHK005 Is "robust historical foundation" translated into measurable criteria (coverage %, data freshness SLA, tolerated missingness)? [Clarity, Ambiguity, Spec §Objective]
- [ ] CHK006 Is "top 100 NBA players" selection logic defined (ranking source, tie-breakers, update cadence)? [Clarity, Gap, Spec §Success Criteria]
- [ ] CHK007 Is "deep situational context" defined with required format constraints (length, structure, provenance, confidence expression)? [Clarity, Ambiguity, Spec §Scope 3]
- [ ] CHK008 Are "similar situations" match-quality expectations quantified (minimum similarity score, result confidence threshold, fallback behavior)? [Clarity, Gap, Spec §Scope 2]

## Requirement Consistency

- [ ] CHK009 Do scope statements and success criteria align on season coverage ("2-3 seasons" vs "last 2 seasons") without conflict? [Consistency, Conflict, Spec §Scope 1, Spec §Success Criteria]
- [ ] CHK010 Are technical constraints consistent with plan tasks (rate-limit expectations vs ingestion throughput assumptions)? [Consistency, Spec §Technical Constraints, Plan §Phase 1]
- [ ] CHK011 Do export enhancement requirements align with success criteria on which Sheets tabs are mandatory (Props only vs additional reporting tabs)? [Consistency, Spec §Scope 3, Spec §Success Criteria]

## Acceptance Criteria Quality

- [ ] CHK012 Can "comprehensive player game logs" be objectively validated with explicit acceptance metrics (player count, game-log completeness, stat coverage thresholds)? [Measurability, Ambiguity, Spec §Success Criteria]
- [ ] CHK013 Can "automatically populated with daily prop predictions" be validated with explicit cadence and completion windows? [Measurability, Gap, Spec §Success Criteria]
- [ ] CHK014 Are confidence and edge acceptance rules defined with numeric thresholds and tie-breaking guidance for borderline cases? [Acceptance Criteria, Gap, Spec §Success Criteria]

## Scenario Coverage

- [ ] CHK015 Are alternate-flow requirements defined for unavailable upstream data (nba_api outage, partial stat payloads, delayed game logs)? [Coverage, Exception Flow, Gap, Spec §Scope 1]
- [ ] CHK016 Are exception-flow requirements defined for Qdrant unavailability during prop export (degraded export format and signaling)? [Coverage, Exception Flow, Gap, Spec §Scope 2-3]
- [ ] CHK017 Are recovery-flow requirements defined for reruns/reconciliation after failed ingestion or failed export attempts? [Coverage, Recovery Flow, Gap, Plan §Phase 1-3]
- [ ] CHK018 Are idempotency requirements defined for repeated daily runs to prevent duplicate Sheets rows or duplicate embeddings? [Coverage, Gap, Plan §Phase 3]

## Edge Case Coverage

- [ ] CHK019 Are boundary requirements defined for players with sparse history (rookies, traded players, injured-return samples)? [Edge Case, Gap, Spec §Scope 1-2]
- [ ] CHK020 Are boundary requirements defined for stat anomalies (missing PRA components, zero-minute games, overtime outliers)? [Edge Case, Gap, Spec §Scope 1]
- [ ] CHK021 Are formatting requirements defined for extreme values in export context (very long analog narrative, null odds, NaN edges)? [Edge Case, Gap, Spec §Scope 3]

## Non-Functional Requirements

- [ ] CHK022 Are performance requirements defined for end-to-end runtime budgets (backfill batch duration, daily export latency)? [Non-Functional, Gap, Spec §Objective, Plan §Phase 3]
- [ ] CHK023 Are observability requirements defined (mandatory logs, error taxonomy, run-level metrics, alert thresholds)? [Non-Functional, Gap, Spec §Technical Constraints]
- [ ] CHK024 Are security/compliance requirements defined for service-account credentials handling and data-access boundaries? [Non-Functional, Dependency, Gap, Spec §Technical Constraints]

## Dependencies & Assumptions

- [ ] CHK025 Are external dependency contracts explicitly documented (nba_api availability assumptions, Qdrant schema/version assumptions, Google Sheets quota assumptions)? [Dependencies, Assumption, Gap, Spec §Technical Constraints]
- [ ] CHK026 Are configuration requirements complete for all required env vars/secrets and their validation behavior at startup? [Dependencies, Completeness, Gap, Spec §Technical Constraints]
- [ ] CHK027 Are assumptions about timezone/day-boundary for "today's slate" explicitly defined to avoid inconsistent exports? [Assumption, Clarity, Gap, Spec §Scope 3]

## Ambiguities & Conflicts

- [ ] CHK028 Is a requirement ID scheme established for traceability from scope items to acceptance criteria and plan tasks? [Traceability, Gap, Spec §Scope, Plan §Phase 1-3]
- [ ] CHK029 Are ambiguous terms ("robust", "deep", "comprehensive") normalized into glossary-level definitions? [Ambiguity, Gap, Spec §Objective, Spec §Success Criteria]
- [ ] CHK030 Are intentional exclusions documented (what is out-of-scope for this track) to reduce requirement drift? [Boundary, Gap, Spec §Scope]

## Notes

- Mark completed checks with `[x]`.
- Record clarification outcomes inline beside each CHK item.
- Add requirement IDs to spec/plan before final review if CHK028 remains open.
