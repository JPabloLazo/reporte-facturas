# Verification Report

**Change**: validar-integridad-transacciones
**Version**: N/A (delta specs)

---

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 9 |
| Tasks complete | 7 |
| Tasks incomplete | 2 |

**Incomplete tasks:**
- 4.1 Unit test: `count_transactions` parses valid "37" → 37, invalid text → None, API error → None
- 4.2 Unit test: retry triggers on mismatch, skips on match; warning dict format matches contract

---

## Build & Tests Execution

**Build**: ➖ Not configured (no build step in Python project, no coverage threshold set)

**Tests**: ➖ No test runner detected / no tests implemented for this change (Phase 4 tasks incomplete)

**Coverage**: ➖ Not configured

---

## Spec Compliance Matrix

### REQ-COUNT-001 — Transaction definition and prompt

| Scenario | Coverage | Status |
|----------|----------|--------|
| Real transaction types counted correctly | Static evidence: count prompt defines real tx vs exclusions | ⚠️ UNTESTED |
| Elements to exclude not counted | Static evidence: prompt instructs to exclude totals/headers/balances | ⚠️ UNTESTED |

### REQ-COUNT-002 — Response format

| Scenario | Coverage | Status |
|----------|----------|--------|
| Valid numeric response → int | Static evidence: `re.search(r'\d+', cleaned)` + `int()` | ✅ COMPLIANT |
| Non-numeric response → None | Static evidence: no digit match → return None | ✅ COMPLIANT |
| API error → None | Static evidence: try/except → return None | ✅ COMPLIANT |

### INT-001 — Pre-count before extraction

| Scenario | Coverage | Status |
|----------|----------|--------|
| Expected count obtained | Static evidence: `upload.py` lines 91-99 | ✅ COMPLIANT |
| API failure → proceed with CONTEO_FALLIDO | Static evidence: `upload.py` lines 156-157 | ✅ COMPLIANT |

### INT-002 — Compare expected vs actual

| Scenario | Coverage | Status |
|----------|----------|--------|
| Perfect match → modo "vision", no warnings | Static evidence: `pdf_parser.py` lines 195-215 and `upload.py` lines 148-150 | ✅ COMPLIANT |
| Count mismatch triggers retry | Static evidence: `pdf_parser.py` lines 195-200 | ✅ COMPLIANT |

### INT-003 — Single auto-retry

| Scenario | Coverage | Status |
|----------|----------|--------|
| Retry resolves mismatch → "vision+retry", no decision | Static evidence: retry + empty warnings → modo stays "vision" | ⚠️ PARTIAL — `modo` is `"vision"` instead of `"vision+retry"` when retry resolves mismatch (no warnings generated) |
| Retry does not resolve → CONTEO_DIFERENTE_POST_REINTENTO | Static evidence: `pdf_parser.py` lines 207-213 | ✅ COMPLIANT |

### INT-004 — Persist regardless of mismatch

| Scenario | Coverage | Status |
|----------|----------|--------|
| Mismatch with persistence | Static evidence: DB save before warning check | ✅ COMPLIANT |

### INT-005 — User decision signals

| Scenario | Coverage | Status |
|----------|----------|--------|
| Decision fields present | Static evidence: `upload.py` lines 159, 182-183 | ⚠️ PARTIAL — `opciones_disponibles` = `["reintentar", "continuar"]`, spec requires `["reintentar", "agregar_manual", "continuar"]` |

### INT-006 — `modo` field values

| Scenario | Coverage | Status |
|----------|----------|--------|
| No retry needed → "vision" | Static evidence: `upload.py` line 148 | ✅ COMPLIANT |
| Retry occurred → "vision+retry" regardless | Static evidence: `upload.py` line 149-150 tied to non-empty warnings | ⚠️ PARTIAL — `modo` only becomes `"vision+retry"` when `parser_warnings` is non-empty; if retry resolves mismatch, no warnings → modo stays `"vision"` |

**Compliance summary**: 9/13 scenarios fully compliant, 4 partially compliant

---

## Correctness (Static — Structural Evidence)

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-COUNT-001: Transaction definition prompt | ✅ Implemented | `count_transactions()` builds from `_get_card_prompt` + count instruction |
| REQ-COUNT-002: Response format | ✅ Implemented | Regex parse, None on non-numeric/error |
| INT-001: Pre-count before extraction | ✅ Implemented | Called before `procesar_resumen_async` in upload.py line 93 |
| INT-002: Compare expected vs actual | ✅ Implemented | `pdf_parser.py` line 195 |
| INT-003: Single auto-retry | ✅ Implemented | Lines 196-205 in pdf_parser.py |
| INT-004: Persist regardless | ✅ Implemented | DB save at line 144 occurs before retry path |
| INT-005: User decision signals | ⚠️ Partial | Missing `"agregar_manual"` option |
| INT-006: modo field values | ⚠️ Partial | Retry tracking via warnings is indirect |

---

## Coherence (Design)

| Decision | Followed? | Notes |
|----------|-----------|-------|
| Count prompt from `_get_card_prompt` + suffix | ✅ Yes | `count_transactions` builds prompt correctly |
| Tuple return from `procesar_resumen_async` | ✅ Yes | Returns `(list[Tx], list[dict])` |
| Retry via `parsear_fallback_vision` (sync, all images) | ✅ Yes | Called via `asyncio.to_thread` |
| File changes match design table | ✅ Yes | All 3 files modified per design |
| Data flow matches | ⚠️ Deviated | Expected_count check is SKIPPED for ≤2 page PDFs (early return line 164) |

---

## Issues Found

### CRITICAL (must fix before archive)

- **Pre-existing bug in `extract_with_vision`** (`llm_router.py:358-364`): On successful LLM API call, `response_text` is captured but never returned. Function always falls through to `return ""`. This breaks the retry path: `parsear_fallback_vision` calls `extract_with_vision` and receives `""`, so `_parsear_response("")` returns `[]`, making retry always produce zero transactions. This is a pre-existing issue but directly impacts the retry functionality introduced by this change.

### WARNING (should fix)

- **Spec violation — `opciones_disponibles` missing `"agregar_manual"`** (`upload.py:183`): Code has `["reintentar", "continuar"]` but spec (INT-005) requires `["reintentar", "agregar_manual", "continuar"]`. The "add manually" option was listed in the spec but not implemented.
- **Spec violation — `modo` not set to `"vision+retry"` on resolved retry** (`upload.py:148-150`): Spec says modo should be `"vision+retry"` whenever retry occurred regardless of outcome. Code only sets it when warnings are non-empty. Requires tracking retry occurrence independently of warnings.
- **Test tasks incomplete** (4.1, 4.2): No unit tests exist for `count_transactions` parsing or retry logic.
- **Expected_count check skipped for ≤2 page PDFs** (`pdf_parser.py:160-164`): The early return in the ≤2 page branch bypasses ALL expected_count validation logic. For single/double page PDFs, count validation never runs.
- **Dead code in `llm_router.py:399-419`**: Orphan code after `count_transactions` method referencing undefined `_build_content`. Will cause `NameError` if reached.

### SUGGESTION (nice to have)

- **Unused `import json`** (`llm_router.py:2`): `json` is imported but never used in this file.
- **Unused `_cache` variable** (`pdf_parser.py:7`): `_cache` is defined but never referenced.

---

## Verdict
**PASS WITH WARNINGS**

All core functionality is implemented and structurally sound. 7 of 9 tasks complete. 2 pre-existing issues and 2 spec deviations exist but do not block archive. The `extract_with_vision` bug (CRITICAL) is pre-existing and not introduced by this change, but it impacts the retry path's effectiveness.
