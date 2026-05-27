# Proposal: Optimizar Rendimiento del Pipeline de Preview

## Intent

El pipeline de preview actual procesa 8 archivos de facturas en ~480s con 100% de timeouts. Necesitamos bajar a <180s sin timeouts vía paralelismo, timeouts más largos y compresión de imágenes.

## Scope

### In Scope
- **A — Paralelismo**: Reemplazar for-loop secuencial con `asyncio.gather()` + `asyncio.wait_for()` por archivo
- **B — Timeout**: Aumentar `timeout=60` → `timeout=120` por archivo
- **C — Compresión de imágenes**: DPI 200→150, JPEG quality 85→60, limitar a últimas 3 páginas
- **D — Response**: Retornar resultados parciales vía `StreamingResponse` conforme terminan

### Out of Scope
- Refactor del LLMRouter como async nativo
- Cache de resultados en Redis/DB
- Optimización del MarkitdownExtractor
- Cambios en el schema de respuesta

## Approach

1. Reemplazar for-loop por `asyncio.gather(*(procesar_archivo(f) for f in sorted_files))` con `return_exceptions=True`
2. Subir `asyncio.wait_for()` timeout de 60s a 120s
3. En rama vision: pasar `dpi=150` a `convert_from_bytes()` y `quality=60` en JPEG; limitar a `pages[-3:]`
4. Cambiar endpoint a `StreamingResponse` que yield resultados parciales vía `async generator`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/services/preview_service.py` | Modified | Gather paralelo, timeout 120s, DPI/quality reducidos |
| `app/routers/preview_router.py` | Modified | Response streaming con `StreamingResponse` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Rate limit del LLM con 8 llamadas paralelas | Medium | `asyncio.Semaphore(4)` para limitar concurrencia |
| Memoria con gather de PDFs grandes | Low | DPI 150 + 3 páginas max reduce footprint; gather libera al completar |
| StreamingResponse rompe cliente existente | Low | El schema de cada chunk es idéntico al actual |

## Rollback Plan

`git checkout -- openspec/changes/optimizar-rendimiento-preview/ app/services/preview_service.py app/routers/preview_router.py`

## Dependencies

Ninguna. Todo el stack necesario ya está implementado (asyncio.gather es stdlib).

## Success Criteria

- [ ] 8 archivos procesados en <180s (vs ~480s actual)
- [ ] 0 timeouts con 8 archivos (vs 100% actual)
- [ ] Cada chunk individual retorna en <120s
- [ ] Imágenes vision ~44% más pequeñas (DPI 150 + quality 60)
