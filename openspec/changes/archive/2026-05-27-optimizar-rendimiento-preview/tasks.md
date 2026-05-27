# Tasks: Optimizar Rendimiento del Pipeline de Preview

**File**: `app/services/preview_service.py`

## Phase 1: Foundation

- [x] 1.1 Change `timeout=60` → `timeout=120` in `asyncio.wait_for()` on line 129

## Phase 2: Image Optimization

- [x] 2.1 In PDF vision branch (lines 64-68): add `dpi=150` to `convert_from_bytes(file_bytes)` on line 64; limit loop to `pages[-3:]` on line 65; set JPEG `quality=60` on line 68
- [x] 2.2 In image vision branch (line 61): change JPEG `quality=85` → `quality=60`

## Phase 3: Parallel Processing

- [x] 3.1 Add `sem = asyncio.Semaphore(4)` after sorted_files (line 124); define nested `async def procesar_con_semaphore(f)` (line 126) that acquires sem then calls `procesar_archivo(f)` with `wait_for(..., timeout=120)`
- [x] 3.2 Replace sequential for-loop (lines 122-137) with `tasks = [procesar_con_semaphore(f) for f in sorted_files]` then `resultados = await asyncio.gather(*tasks)`
- [x] 3.3 Update return on line 144: returns `resultados, False` (partial not applicable with gather — todos los errores ya están capturados por file)
