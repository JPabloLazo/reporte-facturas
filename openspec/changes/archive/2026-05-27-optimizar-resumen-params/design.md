# Design: Optimizar parámetros del pipeline de resumen

## Technical Approach

Four independent parameter changes in two files. No logic restructure, no new interfaces. Data flow remains unchanged. Each change reduces payload size or per-call latency, compounding to bring 221s → target <150s.

## Architecture Decisions

| Decision | Before | After | Rationale |
|----------|--------|-------|-----------|
| `batch_size` | `max(1, n_pages // 3)` | `1` | Smaller batches → faster LLM first-token; Semaphore(3) still provides 3-way concurrency |
| DPI | 150 | 100 | ~54% smaller base64 payload; text at 10pt+ is still legible |
| JPEG quality | 60 | 50 | ~15% smaller per-image; quality loss negligible for printed text |
| Max pages | unlimited | 15 | Hard safety limit against timeouts on abnormally large PDFs |

**Alternatives considered**: Only `batch_size=2` (didn't save enough), `batch_size=n_pages` 1-at-a-time (lost Semaphore parallelism). DPI 72 rejected (too much quality risk).

## Data Flow

```
PDF file ──→ convert_from_path(dpi=100, max_pages=15) ──→ [PIL Images]
       JPEG(quality=50) → base64 → batches(batch_size=1) ──→ LLM vision calls (Semaphore 3)
                                                                    ↓
                                                          ┌── parsear_response
                                                          │   merge + sort
                                                          └── TransaccionExtraida[]
```

Unchanged from baseline — only parameter values differ.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/routers/upload.py:78` | Modify | `dpi=150` → `dpi=100`, add `max_pages=15` to `convert_from_path` |
| `app/routers/upload.py:82` | Modify | `quality=60` → `quality=50` |
| `app/services/pdf_parser.py:179` | Modify | `max(1, n_pages // 3)` → `1` |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Manual | 6-page AMEX resumen | Run before/after benchmark — verify <150s and same extracted fields |
| Manual | VISA & Mastercard samples | Spot-check extraction quality at lower DPI/quality |

## Migration / Rollout

No migration required. Deploy to staging, benchmark 3 known resumen types, then production.

## Open Questions

None.
