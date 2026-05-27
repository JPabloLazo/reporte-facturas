# Design: Optimizar Rendimiento del Pipeline de Preview

## Technical Approach

Replace the sequential for-loop in `preview_service.py` with parallel async execution using `asyncio.gather` + `Semaphore(4)`, extend per-file timeout to 120s, and reduce image payload via lower DPI/quality and page limiting. Only `app/services/preview_service.py` is modified.

## Architecture Decisions

### Decision: Concurrency Model

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `asyncio.gather` + Semaphore | Simple, stdlib, no deps | ✓ Chosen |
| `asyncio.gather(return_exceptions=True)` | Decoupling error handling from gather — each timeout handled in subtask | Rejected — inner try/except per file is more explicit |
| ThreadPoolExecutor | Overkill, complicates error propagation | Rejected |

**Rationale**: Gather is the simplest parallel pattern in stdlib. Semaphore(4) prevents saturating the LLM provider rate limit while still delivering ~4x speedup over sequential.

### Decision: Semaphore = 4

**Rationale**: Proposal measures 8 files → 4 parallel slots → 2 batches → ~2x baseline latency per batch. After fix, each file takes ≤120s → batch of 4 takes ≤120s → 8 files ≤240s worst case. Matches the <180s target for typical case where files finish in 60-90s.

### Decision: Timeout = 120s

**Rationale**: Free-tier LLM calls measured at 60-90s. Per-file timeout matches the provider's worst-case. Previous 60s caused 100% timeout on 8 files.

### Decision: DPI = 150, Quality = 60, Pages = Last 3

**Rationale**: DPI 200→150 reduces pixel count ~44%. Quality 85→60 reduces JPEG size ~40%. Combined ~66% reduction per image. Last 3 pages capture totals/VAT — first pages are line-item detail irrelevant for preview. All three values validated against real invoice images.

## Data Flow

```
BEFORE (per file):

  sorted_files ──→ for f in files ──→ procesar_archivo(f) ──→ resultados.append()
                       │ timeout=60s                           │
                       └───→ TimeoutError → error dict ────────┘
  Total: 8 × 60s = 480s (sequential, ALL timeout)

AFTER (per file):

  sorted_files ──→ [procesar_con_semaphore(f) for f in files]
                       │
                  asyncio.gather(*tasks)
                       │
              ┌────────┼────────┐
          Semaphore(4)  │   Semaphore(4)
              │         │         │
          batch 1    batch 1   batch 2
          (files 1-4)(files 5-8)
              │                   │
         wait_for(120s)      wait_for(120s)
              │                   │
         ┌────┴────┐         ┌───┴────┐
       success  timeout    success  timeout
         │        │          │        │
         └────────┴──────────┴────────┘
              resultados (list[dict])
  Total: 8 files × Semaphore(4) → ~120-180s
```

### Image compression per vision file

```
convert_from_bytes(file_bytes, dpi=150)
       │
   pages[-3:]  ← last 3 pages
       │
   page.convert("RGB").save(JPEG, quality=60)
       │
   base64.b64encode() → images_base64 (66% smaller)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/services/preview_service.py` | Modify | A: sequential for-loop → asyncio.gather + Semaphore(4); B: timeout 60→120; C: DPI 200→150, quality 85→60, pages[-3:] |

## Interfaces / Contracts

No new interfaces. `extract_preview()` returns the same `tuple[list[dict], bool]` — contracts unchanged. Error dict shape within list matches current format.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Semaphore limits N concurrent tasks | Mock `procesar_archivo` with `asyncio.sleep`, assert ≤4 concurrent |
| Unit | Timeout 120s applies per file | Mock slow call, assert error dict returned |
| Integration | 8 real files complete <180s | Run against staging Drive folder with instrumented timing |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM rate limit with 4 parallel calls | Low | Semaphore(4) is conservative for most providers |
| gather holds all results in memory | Low | 8 files × ~3 images × ~200KB = ~4.8MB — negligible |
| Quality loss at JPEG 60 impacts extraction | Low | OCR/text extraction works on text regions, not photo quality |

## Open Questions

- None. All decisions are validated against existing data.
