# Design: Validar integridad de transacciones extraídas

## Technical Approach

Wrap the extraction pipeline with a pre-count validation step. A new `count_transactions()` call (all images, single LLM call) gets the expected count before extraction. After extraction, compare actual vs expected — on mismatch, retry once with all images in a single call (`parsear_fallback_vision`). The result propagates structured warnings and a `requiere_decision_usuario` signal to the response.

## Architecture Decisions

### Decision: Count prompt format

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Card-specific + count suffix | More accurate per card type | **Chosen** — reuse `_get_card_prompt` + append "CONTÁ SOLO las transacciones, respondé SOLO el número" |
| Generic count prompt | Simpler but less accurate for AMEX (table layout) | Rejected |
| Per-page count, sum result | Risk of double-counting split transactions | Rejected |

### Decision: Tuple return from `procesar_resumen_async`

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Return `(list[Tx], list[dict])` | Breaks API, single caller to fix | **Chosen** — only `upload.py` calls it |
| Add separate async method | Duplication | Rejected |
| Append warnings to response in parser | Side effect, hard to test | Rejected |

### Decision: Retry calls `parsear_fallback_vision` (all images, sync)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Call existing sync method | Simple, already wraps all images | **Chosen** — wrapped in `asyncio.to_thread` inside `procesar_resumen_async` |
| Build new retry prompt path | Duplicates logic | Rejected |

## Data Flow

```
images_b64
    │
    ▼
LLMRouter.count_transactions(images, card_type)
    │  [single LLM call, all images]
    │  returns: int | None
    ▼
procesar_resumen_async(images, llm, card_type, expected_count)
    │
    ├─ batch extraction (existing parallel logic)
    │   └─ all_tx: list[TransaccionExtraida]
    │
    ├─ if expected_count and len(all_tx) != expected_count:
    │    └─ all_tx = parsear_fallback_vision(ALL images) [sync, single call]
    │       └─ re-compare, if still mismatch → add warning dict
    │
    └─ return (all_tx, warnings_parser)
              │         └─ list[dict] (empty if ok)
              ▼
    upload.py unpacks tuple, merges warnings, builds response
```

## File Changes

| File | Lines | Changes |
|------|-------|---------|
| `app/services/llm_router.py` | +15 | New `count_transactions(self, images, card_type) -> int \| None` — builds count prompt from `_get_card_prompt` + "CONTÁ SOLO las transacciones. Respondé SOLO un número entero."; calls `extract_text_with_prompt`; parses `int()` from response |
| `app/routers/upload.py` | +20 | Call `llm.count_transactions()` before extraction (~line 89); unpack tuple from parser; merge warnings; set `modo`, `requiere_decision_usuario`, `opciones_disponibles` in response |
| `app/services/pdf_parser.py` | +30 | `procesar_resumen_async` accepts `expected_count: int \| None = None`; after extraction compare len vs expected; retry via `parsear_fallback_vision` (all images); return `(list[Tx], list[dict])` |

## Interfaces / Contracts

```python
# llm_router.py
class LLMRouter:
    def count_transactions(self, images: list[str], card_type: str = "GENERIC") -> int | None:
        """Single LLM call counting visible transactions. Returns int or None on failure."""
```

```python
# pdf_parser.py — changed signature
@staticmethod
async def procesar_resumen_async(
    images_b64: list[str],
    llm_router,
    card_type: str = "GENERIC",
    expected_count: int | None = None,
) -> tuple[list[TransaccionExtraida], list[dict]]:
    """Returns (transactions, warnings).
    Warnings format: [{"codigo": "...", "mensaje": "...", ...}]
    """
```

```python
# upload.py response — extended
{
    "id": ...,
    "tipo": ...,
    "modo": "vision" | "vision+retry",
    "transacciones": [...],
    "warnings": [
        {"codigo": "TARJETAS_SIN_MAPEO", ...},
        {"codigo": "CONTEO_FALLIDO", "mensaje": "No se pudo determinar el conteo esperado"},
        {"codigo": "CONTEO_DIFERENTE_POST_REINTENTO", "esperadas": N, "extraidas": M, "diferencia": N-M},
    ],
    "requiere_decision_usuario": True,
    "opciones_disponibles": ["reintentar", "continuar"]
}
```

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | `count_transactions()` parse logic | Mock LLM response, test int parse and None on failure |
| Unit | Retry trigger logic | Mock `parsear_fallback_vision`, verify it's called only on mismatch |
| Unit | Warning dict format | Verify structure matches contract |
| Integration | Full pipeline with known PDF | Real LLM call, compare count stability across 10 runs |

## Migration / Rollout

No migration required. The `expected_count` param defaults to `None` — existing calls without it work identically (no count, no validation). Only `upload.py` is updated to pass the count.

## Open Questions

- None
