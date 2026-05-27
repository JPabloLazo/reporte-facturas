# Integrity — Transaction Count Validation Pipeline

## Purpose

Validation layer that compares LLM-pre-counted transactions against extracted results, with auto-retry and user decision escalation.

## Requirements

### Requirement: INT-001 — Pre-count before extraction

The system SHALL call `LLMRouter.count_transactions()` with ALL page images before extraction begins.

#### Scenario: Expected count obtained

- GIVEN a PDF with 37 real transactions
- WHEN `count_transactions` returns 37
- THEN extraction SHALL proceed with `expected_count=37`

#### Scenario: API failure during count

- GIVEN an API failure in `count_transactions`
- WHEN the call returns None
- THEN extraction SHALL proceed without expected count
- AND the warning list SHALL include "CONTEO_FALLIDO"

### Requirement: INT-002 — Compare expected vs actual

The system SHALL compare expected count with extracted transaction count.

#### Scenario: Perfect match

- GIVEN expected=37 and 37 transactions extracted
- THEN `modo` SHALL be `"vision"`
- AND the integrity warning list SHALL be empty

#### Scenario: Count mismatch triggers retry

- GIVEN expected=37 and 35 transactions extracted
- THEN the system SHALL auto-retry by re-processing ALL images

### Requirement: INT-003 — Single auto-retry

The system SHALL auto-retry exactly ONCE on count mismatch.

#### Scenario: Retry resolves mismatch

- GIVEN expected=37 and 35 extracted on first pass
- WHEN retry yields 37 transactions
- THEN `modo` SHALL be `"vision+retry"`
- AND `requiere_decision_usuario` SHALL be `false`

#### Scenario: Retry does not resolve mismatch

- GIVEN expected=37 and 35 extracted on first pass
- WHEN retry still yields 35 transactions
- THEN `requiere_decision_usuario` SHALL be `true`
- AND warning list SHALL include "CONTEO_DIFERENTE_POST_REINTENTO"

### Requirement: INT-004 — Persist regardless of mismatch

The system SHALL always save extracted transactions to DB.

#### Scenario: Mismatch with persistence

- GIVEN a count mismatch after retry
- WHEN extraction completes
- THEN all extracted transactions SHALL be persisted
- AND the warning list SHALL include mismatch details

### Requirement: INT-005 — User decision signals

The response JSON SHALL include decision fields when mismatch persists after retry.

#### Scenario: Decision fields present

- GIVEN a persistent mismatch after retry
- THEN `requiere_decision_usuario` SHALL be `true`
- AND `opciones_disponibles` SHALL be `["reintentar", "agregar_manual", "continuar"]`

### Requirement: INT-006 — `modo` field values

The `modo` field SHALL reflect integrity state.

#### Scenario: No retry needed

- GIVEN a run with no count mismatch
- THEN `modo` SHALL be `"vision"`

#### Scenario: Retry occurred

- GIVEN a run where auto-retry happened
- THEN `modo` SHALL be `"vision+retry"` regardless of whether retry resolved the mismatch
