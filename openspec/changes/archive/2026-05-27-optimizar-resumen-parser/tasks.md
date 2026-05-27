# Tasks: Optimizar parser de resúmenes de tarjetas

## Phase 0: Critical fix — non-blocking upload

- [x] 0.1 `app/routers/upload.py:77-82` — Wrap `convert_from_path` and the JPEG encode loop in `asyncio.to_thread()` so the event loop stays responsive
- [x] 0.2 `app/routers/upload.py:83` — Wrap `ResumenParser.parsear_fallback_vision(images_b64, llm_instance)` in `asyncio.to_thread()`, pass `card_type=tipo_fallback`

## Phase 1: Card-type-aware prompts

- [x] 1.1 `app/services/llm_router.py:216` — Add class-level `PROMPTS_BY_TYPE` dict with an AMEX prompt (numbered search strategy, specific layout hints like `"Nro. de Socio"`)
- [x] 1.2 `app/services/llm_router.py` — Add VISA prompt to `PROMPTS_BY_TYPE` (numbered strategy, layout hints for `"Nro. de Tarjeta"`), Mastercard entry as alias to VISA
- [x] 1.3 `app/services/llm_router.py:216` — Add `card_type: str | None = None` param to `extract_with_vision`; select prompt from `PROMPTS_BY_TYPE.get(card_type, GENERIC_PROMPT)` with generic as fallback

## Phase 2: Multi-page parallel processing + validation

- [x] 2.1 `app/services/pdf_parser.py` — Added `procesar_resumen_async()`: ≤2 pages → single call via to_thread; ≥3 pages → batches via `asyncio.gather` + `Semaphore(3)`, merge sorted by fecha. Added `_parsear_response()` helper. Updated upload.py to use the new async method.
- [x] 2.2 `app/services/pdf_parser.py` — Create `validar_extraccion(transacciones, metadata) -> list[str]` static method: check count match, sum vs total, date range within period, consecutive identical duplicates

## Phase 3: Optimization

- [x] 3.1 `app/routers/upload.py:81` — Change JPEG quality from 70 to 60 in the `img.save()` call
- [x] 3.2 `app/static/js/main.js:153-158` — In the `.catch` handler of `uploadFile()`: reset `file-input.value = ''` and add class `hidden` to `file-info`

## Phase 4: Date format + caching

- [x] 4.1 `app/services/pdf_parser.py` — Normalize all returned dates to `DD-MM-YYYY` in response. Add module-level `_cache` dict for future caching.
