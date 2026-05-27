# Proposal: Validar integridad de transacciones extraídas

## Intent

The same AMEX PDF (6 pages) produces inconsistent transaction counts (37, 38, or 40) across LLM calls due to non-deterministic behavior. Users silently get incomplete data. We need a validation layer that detects omissions and offers recovery.

## Scope

### In Scope
- `LLMRouter.count_transactions()` — lightweight pre-count prompt
- Validation + auto-retry (max 1 retry) in extraction pipeline
- `modo="vision+retry"` and `requiere_decision_usuario` signal
- Frontend modal for user decision (retry, add manual, continue)

### Out of Scope
- Backend endpoint for manual transaction addition (frontend-only)
- Multiple retry cycles (max 1)
- Persisting retry history in DB
- Validation for non-AMEX card types

## Approach

**Fase 1 — Conteo previo**: New `count_transactions()` method counts only real transactions with a minimal prompt. Returns `int | None`.

**Fase 2 — Extracción**: Existing flow unchanged.

**Fase 3 — Validación + Retry**: Compare extracted vs expected count. On mismatch, re-process ALL images with stricter prompt (`parsear_fallback_vision`). If still mismatched, set `modo="vision+retry"` + `requiere_decision_usuario=true`.

**Fase 4 — Decisión usuario**: Frontend shows modal with 3 options — retry (re-call upload), add manually (inline), continue.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/services/llm_router.py` | Modified | Add `count_transactions()` method |
| `app/routers/upload.py` | Modified | Call count before extraction, pass expected count, handle mismatch |
| `app/services/pdf_parser.py` | Modified | Accept expected count, retry logic, return warnings tuple |
| Frontend (Jinja2/JS) | Modified | Modal for user decision on mismatch |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM count also non-deterministic | Medium | On count API failure, continue without validation + warning |
| Retry produces same mismatch | Medium | User decides; DB saves mismatch result anyway |
| Extra LLM call adds latency | Low | Pre-count prompt is lightweight (~10-15s) |

## Rollback Plan

Remove `count_transactions()` call and `expected_count` param from `upload.py` and `pdf_parser.py`. Restore original extraction-only flow.

## Dependencies

- LLM provider API must support a second call per upload (2 total: count + extraction)

## Success Criteria

- [ ] 10 consecutive runs on same AMEX PDF produce identical transaction counts
- [ ] User sees decision modal when mismatch detected
- [ ] All 3 user options work (retry, add, continue)
