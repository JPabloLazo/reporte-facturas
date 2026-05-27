# Proposal: Optimizar parámetros del pipeline de resumen

## Intent

6-page AMEX resumen takes 221s → 83% is LLM calls. Adjust pipeline params to bring processing under 120s without meaningful quality loss.

## Scope

### In Scope
1. Reduce `convert_from_path` DPI from 150→100 in `upload.py`
2. Reduce JPEG `quality` from 60→50 in `upload.py`
3. Change `batch_size` formula: `max(1, n_pages // 3)` → `1` (1 page per LLM call)
4. Add `max_pages=15` guard to `convert_from_path` in `upload.py`

### Out of Scope
- PDF parser prompt changes (same prompts, just faster)
- Preview service params (separate concern, lower frequency)
- Caching or parallelization architecture

## Approach

Four independent parameter changes, all tune-only (no logic restructure). Apply and benchmark against the 6-page AMEX dataset.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/routers/upload.py:78` | Modified | DPI 150→100, max_pages=15 |
| `app/routers/upload.py:82` | Modified | JPEG quality 60→50 |
| `app/services/pdf_parser.py:179-180` | Modified | batch_size: 2→1 per batch |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| DPI 100 misses very small print | Low | Printed resúmenes use 10pt+ fonts; verify on AMEX 6-pager |
| JPEG 50 degrades OCR | Low | LLM reads text, not images; printed text survives 50 |
| `max_pages=15` silently truncates longer docs | Low | No known resumen exceeds 15 pages; add warning log |

## Rollback Plan

`git checkout -- app/routers/upload.py app/services/pdf_parser.py`

## Dependencies

None.

## Success Criteria

- [ ] 6-page AMEX resumen processes in <150s (from 221s ~32%+ reduction)
- [ ] No extraction errors on 3 known resumen types (AMEX, VISA, Mastercard)
- [ ] All extracted fields (card type, period, totals, transactions) match pre-change output
