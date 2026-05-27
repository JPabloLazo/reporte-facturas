# Tasks: Validar integridad de transacciones extraídas

## Phase 1: Foundation — LLMRouter

- [x] 1.1 Add `count_transactions(self, images, card_type)` to `LLMRouter` — builds prompt from `_get_card_prompt` + count instruction, calls `extract_text_with_prompt`, parses `int()` from response, returns `None` on any error

## Phase 2: Core — Parser retry logic

- [x] 2.1 Change `procesar_resumen_async` signature: add `expected_count: int | None = None`, return `tuple[list[TransaccionExtraida], list[dict]]`
- [x] 2.2 After extraction+sorting, compare `len(all_tx)` vs `expected_count` — on mismatch (<) call `parsear_fallback_vision` (all images, via `asyncio.to_thread`), if improved use retry result
- [x] 2.3 If still mismatched after retry, append warning `{"codigo": "CONTEO_DIFERENTE_POST_REINTENTO", ...}` to warnings list; always return `(all_tx, parser_warnings)`

## Phase 3: Integration — Upload endpoint

- [x] 3.1 Call `llm_instance.count_transactions(images_b64, tipo_fallback)` before extraction, store `expected_count`
- [x] 3.2 Update `procesar_resumen_async` call to unpack tuple + pass `expected_count`
- [x] 3.3 Build `modo`, `all_warnings`, `requiere_decision_usuario`, `opciones_disponibles`; update return dict

## Phase 4: Tests

- [ ] 4.1 Unit test: `count_transactions` parses valid "37" → 37, invalid text → None, API error → None
- [ ] 4.2 Unit test: retry triggers on mismatch, skips on match; warning dict format matches contract
