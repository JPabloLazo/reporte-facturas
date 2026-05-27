# Design: Optimizar parser de resúmenes de tarjetas

## Technical Approach

Non-blocking upload via `asyncio.to_thread`, structured LLM prompts routed by detected card type, multi-page parallel processing with Semaphore(3), and post-extraction warnings. Follows the same concurrency pattern proven in `preview_service.py`.

## Architecture Decisions

### Decision: Async wrapping

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `asyncio.to_thread` for `convert_from_path` + LLM call | Simple, proven in preview_service | ✓ Chosen |
| Custom thread pool | Overkill, same result | Rejected |
| `run_in_executor` | More verbose, same semantics | Rejected |

**Rationale**: `asyncio.to_thread` wraps any sync call into a thread — identical pattern to preview_service. Two calls: one for `convert_from_path`, one for `parsear_fallback_vision`. Upload no longer blocks the event loop.

### Decision: Card type → prompt routing

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `card_type` param on `extract_with_vision` + static prompt dict | Minimal API change, backward-compatible | ✓ Chosen |
| New method per card type | Duplication | Rejected |
| Config-driven prompts | Over-engineering for 3 variants | Rejected |

**Rationale**: `extract_with_vision(images, card_type="AMEX")` reads prompt from a class-level dict `PROMPTS_BY_TYPE`. Generic prompt is default. Reuses `detectar_tipo()` output already computed in upload.py:92.

### Decision: Multi-page processing

| Option | Tradeoff | Decision |
|--------|----------|----------|
| 1st page for metadata, rest in `asyncio.gather` + Semaphore(3) | Parallel speedup, proven gather pattern | ✓ Chosen |
| Process all pages sequentially | Simple but slow | Rejected |
| Process all pages with gather (no semaphore) | Risk of LLM rate-limit | Rejected |

**Rationale**: Same `asyncio.gather` + Semaphore pattern as preview_service. Metadata (card type, total, dates) from page 1 guides prompt selection for remaining pages. Semaphore(3) is conservative.

### Decision: Validation

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Post-merge warnings list | Non-blocking, never crashes upload | ✓ Chosen |
| Hard validation — raise on mismatch | Blocks upload with partial data | Rejected |

**Rationale**: Validation adds `warnings` to the existing response structure. Never prevents returning results.

### Decision: Cache

| Option | Tradeoff | Decision |
|--------|----------|----------|
| `functools.lru_cache` on `procesar_resumen()` | Zero deps, in-memory, auto-evict | ✓ Chosen |
| Custom TTL dict | More control but unnecessary | Rejected |

**Rationale**: lru_cache with `maxsize=32`. Key = `hashlib.md5(pdf_bytes).hexdigest()`. Same pattern as stdlib caching.

## Data Flow

```
Upload flow (AFTER):

  POST /api/upload
       │
   asyncio.to_thread(convert_from_path, dpi=150)
       │
   images_pil (offloaded from event loop)
       │
   tipo = ResumenParser.detectar_tipo(save_path)   ← already sync, fast
       │
   images_b64 = [encode(img) for img in images_pil]
       │
   asyncio.to_thread(
       ResumenParser.parsear_fallback_vision,
       images_b64, llm_instance, card_type=tipo
   )
       │
   transacciones_extraidas (offloaded from event loop)
       │
   DB persist (async) ──→ return response+validation_warnings

Multi-page detail (inside parsear_fallback_vision):

  images[0] ──→ extract metadata (card_type from text)
       │
  selected_prompt = PROMPTS_BY_TYPE.get(card_type, GENERIC_PROMPT)
       │
  images[1:] ──→ asyncio.gather(
       │         extract_transactions(img, prompt)  × N
       │         with Semaphore(3)
       │     )
       │
  merge all ──→ validate(merged)
       │
  return TransaccionExtraida[]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/routers/upload.py` | Modify | Lines 77-83 wrapped in `asyncio.to_thread()`; pass `tipo_fallback` to parser |
| `app/services/llm_router.py` | Modify | Add `PROMPTS_BY_TYPE` dict; `extract_with_vision` accepts optional `card_type` param |
| `app/services/pdf_parser.py` | Modify | New `procesar_resumen()` method with multi-page + Semaphore; `validar_extraccion()` static; `@lru_cache` wrapper |
| `app/static/js/main.js` | Modify | In `uploadFile` error handler (line 153-158): reset `file-input.value=''` and hide `file-info` |

## Interfaces / Contracts

`extract_with_vision(self, images: list[str], task_type="vision", card_type=None) -> str` — new optional `card_type` param. When provided, selects prompt from `PROMPTS_BY_TYPE[card_type]`.

`ResumenParser.procesar_resumen(images_b64, llm_instance, card_type) -> list[TransaccionExtraida]` — new method handling metadata extraction (page 1) + parallel transaction pages.

`ResumenParser.validar_extraccion(transacciones, metadata) -> list[str]` — warnings only, never raises.

Response `warnings` array extended with validation codes (e.g., `"MONTO_NO_COINCIDE"`, `"FECHAS_INCONSISTENTES"`).

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `asyncio.to_thread` doesn't block event loop | 2 concurrent uploads with mocked LLM, assert interleaving |
| Unit | Card type → prompt selection | Mock `PROMPTS_BY_TYPE`, assert correct prompt used |
| Integration | Real PDF (AMEX, VISA, MC) processes in <30s | Manual run with timing instrumentation |
| Integration | Validation warns on mismatched totals | Inject bad data, assert warnings in response |

## Migration / Rollout

No migration required. Bug 0 can be deployed independently. Phases 1-4 deployed together. Rollback: revert commits per phase.

## Open Questions

- None. All decisions are validated against existing patterns in preview_service.
