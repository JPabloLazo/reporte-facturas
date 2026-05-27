# Tasks: Optimizar Pipeline Preview

## Phase 1: Foundation

- [x] 1.1 Add `import asyncio` to `preview_service.py` (line 5, after existing stdlib imports)
- [x] 1.2 Add `extract_fields_from_images(images_base64, llm_router)` static method to `InvoiceExtractor` in `llm_extractor.py`. Accepts `list[str]` base64 images + `LLMRouter`, returns JSON via single vision LLM call. Reuses existing retry/parse logic from `extract_fields_from_markdown()`
- [x] 1.3 Update date format in `llm_extractor.py:20-21`: change both `formato YYYY-MM-DD` to `formato DD-MM-YYYY` in the system prompt
- [x] 1.4 Add `cuota_numero` to JSON schema in `llm_extractor.py:17-26` — insert `"cuota_numero": string | null` between `"numero_factura"` and `}`

## Phase 2: Core Implementation

- [x] 2.1 Remove `INVOICE_VISION_PROMPT` constant (`preview_service.py:17-21`). Replace vision path block (`preview_service.py:62-81`): remove `extract_text_with_prompt` + `extract_fields_from_markdown` 2-step flow, call single `InvoiceExtractor.extract_fields_from_images()` instead
- [x] 2.2 Change `convert_from_bytes(file_bytes, first_page=1, last_page=1)` → `convert_from_bytes(file_bytes)` at `preview_service.py:66` to process all PDF pages. For multi-page: collect all page images into `images: list[Image]`, encode each to base64, pass list to `extract_fields_from_images()`
- [x] 2.3 Wrap both sync LLM calls in `procesar_archivo()` with `await asyncio.to_thread()` — `llm_router.extract_text_with_prompt()` at `preview_service.py:74` and `InvoiceExtractor.extract_fields_from_markdown()` at `preview_service.py:79,83`
- [x] 2.4 Replace global 120s timeout (`preview_service.py:112-118`) with `await asyncio.wait_for(procesar_archivo(f), timeout=60)` per file. Catch `asyncio.TimeoutError` per file and mark that file as error, continue processing others
- [x] 2.5 Add file-type reorder: split `target_files` (`preview_service.py:42-50`) into `markdown_files` and `vision_files`. Process markdown files first (sequential loop), then vision files — yield partial results as they complete

## Phase 3: Verification

- [ ] 3.1 Verify non-blocking: run `extract_preview()` with 2+ files, confirm event loop stays responsive during LLM calls (check asyncio debug logging or concurrent request handling)
- [ ] 3.2 Verify single-call: count LLM calls before/after — each file must make exactly 1 call (vision files go to `extract_fields_from_images`, markdown files to `extract_fields_from_markdown`)
- [ ] 3.3 Verify multi-page: process a PDF with 3+ pages, confirm `datos` includes totals/VAT from last page (was silently omitted before)
- [ ] 3.4 Verify timeout isolation: inject a mock file that sleeps 90s — confirm it times out at 60s and other files complete normally
- [ ] 3.5 Verify reorder: process mixed markdown + vision files, confirm markdown results appear first in `resultados`
