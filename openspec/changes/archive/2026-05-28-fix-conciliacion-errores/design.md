# Design: fix-conciliacion-errores

## Technical Approach

Three isolated, low-risk fixes targeting two files. No schema changes, no data flow changes, no new dependencies. Each fix addresses a distinct failure mode discovered during factura reconciliation.

## Architecture Decisions

### Decision 1: Explicit FacturaDatos Construction

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `**extraccion` | Passes `raw_response` key → SQLAlchemy `TypeError` on unknown column | Rejected |
| Explicit field mapping | Slightly more verbose, zero runtime surprises | **Chosen** |

The `_extraer_datos_factura` helper returns a dict containing `raw_response` (debug key). Using `**extraccion` splats this non-column key into the constructor. Explicit mapping filters it out. Pattern already established in `save_preview_facturas` at `process.py:227-239`.

### Decision 2: Initialize `response` Before Try Block

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Current (no init) | Both LLM calls can fail → `UnboundLocalError` at `response[:500]` | Rejected |
| `response = ""` before try | One line, zero cost | **Chosen** |

The fallback `except` block at `llm_extractor.py:117-131` reads `response[:500]`. If the second `llm_router.chat()` call (line 92) also raises before assigning `response`, the variable is unbound.

### Decision 3: Per-Factura Error Isolation

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Current (no isolation) | Any failed factura kills the entire reconciliation | Rejected |
| try/except + counter | Degrades gracefully; client sees error count | **Chosen** |

Adding `errores_extraccion` counter and wrapping the download→extract→save block in `try/except Exception`. On failure: log, increment, `continue`. Returns `"facturas_con_error"` in response.

## Data Flow

```
process_reconciliation()
  │
  ├── [loop over pdf_files]
  │     try:
  │       download → convert → extract → FacturaDatos(factura_id=factura.id, monto_total=..., ...)
  │     except Exception:
  │       errores_extraccion += 1  ← NEW
  │       continue                 ← NEW
  │
  ├── Conciliador.conciliar(...)
  │
  └── return {
        "facturas_procesadas": facturas_creadas,
        "facturas_con_error": errores_extraccion,  ← NEW
        "resultados": [...],
        ...
      }
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/routers/process.py` | Modify | Fix 1: explicit FacturaDatos mapping. Fix 3: try/except per factura + error counter |
| `app/services/llm_extractor.py` | Modify | Fix 2: initialize `response = ""` before first try block |

## Interfaces / Contracts

Response body gains one new field:

```python
return {
    "facturas_procesadas": facturas_creadas,
    "facturas_con_error": errores_extraccion,  # NEW — int >= 0
    ...
}
```

All existing fields (`resumen_id`, `periodo`, `resultados`, `resumen`) unchanged.

## Testing Strategy

No test framework present in project. Verification via:
- Manual: POST to `/api/process/process` with a PDF folder containing both good and corrupted files
- Assert: returns 200 with `"facturas_con_error"` > 0, successful facturas still processed
- Assert: no `UnboundLocalError` or `TypeError` in application logs

## Migration / Rollout

No migration required. Backward-compatible — existing clients ignore the new field.

## Open Questions

None.
