# Proposal: fix-conciliacion-errores

## Intent

`/api/process/process` returns silent 500 on extraction failures. Three bugs cascade: invalid kwargs passed to `FacturaDatos` constructor (`process.py:66`), `UnboundLocalError` on uninitialized variable (`llm_extractor.py:120`), and no per-factura error isolation. Each crashed factura kills the entire process.

## Scope

### In Scope
- Explicit field mapping in `FacturaDatos()` construction — no `**extraccion`
- Initialize `response = ""` before LLM try block in `llm_extractor.py`
- Wrap per-factura processing in try/except, accumulate errors, return in response

### Out of Scope
- LLM prompt improvements or model changes
- Retry logic for failed extractions
- Adding tests (no test framework present)

## Approach

Three targeted fixes:

1. **process.py** — Replace `FacturaDatos(factura_id=x, **extraccion)` with explicit constructor args (`factura_id`, `total_factura`, `fecha_factura`, `total_iva`, `total_isr`) to filter out `raw_response` and other non-column keys.
2. **llm_extractor.py** — Add `response = ""` before the first try block so line 120's `response[:500]` never hits `UnboundLocalError`.
3. **process.py** — Wrap the factura processing loop body in `try/except Exception`, log the error, increment a counter, and continue. Return `errors` count alongside results.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/routers/process.py` | Modified | Fix 1 (explicit mapping) + Fix 3 (per-factura resilience) |
| `app/services/llm_extractor.py` | Modified | Fix 2 (initialize response) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Missed a FacturaDatos column in explicit mapping | Low | Cross-reference with the model; tests catch missing columns at runtime |
| Error on skipped factura masks real bugs | Med | Log full exception; return error count to client for visibility |

## Rollback Plan

Revert the two files (`git checkout -- app/routers/process.py app/services/llm_extractor.py`). The endpoint returns to previous behavior.

## Dependencies

None. All changes are isolated to two files.

## Success Criteria

- [ ] `/api/process/process` returns 200 with results even when one factura extraction fails
- [ ] Error count in response body reflects failed facturas
- [ ] No `UnboundLocalError` or `TypeError` in logs during extraction
