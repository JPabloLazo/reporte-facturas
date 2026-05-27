# Proposal: Optimizar parser de resúmenes de tarjetas

## Intent

El upload de resúmenes de tarjeta bloquea el event loop de FastAPI y usa prompts genéricos que producen extracciones inconsistentes. Necesitamos hacerlo async, estructurar prompts por tipo de tarjeta, y validar resultados post-extracción.

## Scope

### In Scope

- **Bug 0**: Envolver `convert_from_path` y `parsear_fallback_vision` en `asyncio.to_thread` para no bloquear el event loop
- **Phase 1**: Prompts estructurados para AMEX, VISA, Mastercard con búsqueda ordenada (como invoice_extractor.py)
- **Phase 2**: Procesar página 1 aparte + páginas de transacciones en paralelo con `asyncio.gather` + `Semaphore(3)`
- **Phase 3**: Validación post-extracción (conteo vs total, rango fechas, duplicados)
- **Phase 4**: quality=60, fechas DD-MM-YYYY, caché por hash de PDF

### Out of Scope

- Nuevos tipos de tarjeta (solo AMEX/VISA/Mastercard)
- UI de feedback paravalidación (solo backend)
- Cache persistente en DB (solo en memoria)

## Approach

1. Bug 0: `asyncio.to_thread` para pdf2image y LLM call en upload.py
2. Phase 1: `TarjetaPromptFactory` en llm_router.py con prompts por tipo + estrategia de búsqueda ordenada
3. Phase 2: `procesar_resumen()` en pdf_parser.py extrae página 1, luego gather+Semaphore(3) para resto
4. Phase 3: `validar_extraccion()` post-merge — checksums, fechas, duplicados
5. Phase 4: quality=60, `strftime("%d-%m-%Y")`, dict cache por `hashlib.md5(pdf_bytes)`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/routers/upload.py` | Modified | Wrapping síncrono en to_thread |
| `app/services/llm_router.py` | Modified | Nuevos prompts por tarjeta |
| `app/services/pdf_parser.py` | Modified | Multi-page + caché |
| `app/static/js/main.js` | Modified | Reset UI tras error |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Semaphore(3) + parallel pages satura LLM | Low | 3 es conservador, igual que Semaphore(4) en preview |
| Prompts estructurados rompen tarjetas existentes | Low | Mantener prompt genérico como fallback |
| quality=60 degrada OCR | Low | Validado en preview_service — texto se mantiene legible |

## Rollback Plan

Revert commits por fase. Bug 0 es independiente — se puede revertir solo. Phases 1-4 comparten pdf_parser.py, revertir juntos si hay problemas.

## Dependencies

- Ninguna externa. Todo stdlib (`asyncio`, `hashlib`, `functools.lru_cache`).

## Success Criteria

- [ ] Upload no congela el event loop (verificar con 2 uploads simultáneos)
- [ ] AMEX, VISA, Mastercard se parsean correctamente (validación manual con 3 resúmenes reales cada uno)
- [ ] PDF de 10 páginas se procesa en <30s (vs ~60s actual)
- [ ] Validación detecta transacciones faltantes o duplicadas
