# Design: Optimizar Pipeline Preview

## Technical Approach

Fix 4 bugs + reorder pipeline in `preview_service.py` and `llm_extractor.py`. Sync LLM calls get wrapped in `asyncio.to_thread()`, the vision double-call is replaced by a single unified LLM call per file, all PDF pages are converted, and per-file timeout replaces the global 120s window.

## Architecture Decisions

### Decision: `asyncio.to_thread()` for sync LLM calls

**Choice**: Wrap `llm_router.extract_text_with_prompt()` and `InvoiceExtractor.extract_fields_from_markdown()` in `asyncio.to_thread()` in the already-async `procesar_archivo()`.  
**Alternatives**: Rewrite LLMRouter as async-native (touches 6 provider implementations). Leave as-is (blocks event loop).  
**Rationale**: LLMRouter creates fresh `httpx.Client`/`anthropic.Anthropic`/`openai.OpenAI` per call — thread-safe by construction. Zero risk, minimal diff.

### Decision: Unified Vision Agent (1 LLM call per file)

**Choice**: Add `InvoiceExtractor.extract_fields_from_images(images_base64, llm_router)` that takes all page images and returns JSON directly via a single vision LLM call.  
**Alternatives**: Keep 2-call pattern (extract_text_with_prompt → extract_fields_from_markdown).  
**Rationale**: Modern multimodal LLMs (Claude 3.5, GPT-4o) output structured JSON from images directly. Halves latency and cost for vision files. Reuses existing retry/JSON-parse logic from `extract_fields_from_markdown()`.

### Decision: Convert all PDF pages

**Choice**: `convert_from_bytes(file_bytes)` without page limits = all pages.  
**Alternatives**: Keep `first_page=1, last_page=1` (missing data on later pages).  
**Rationale**: Totals, VAT breakdown, and provider info often on last page. Performance impact is negligible — pdf2image is fast and memory-efficient.

### Decision: Per-file `asyncio.wait_for()` timeout

**Choice**: `await asyncio.wait_for(procesar_archivo(f), timeout=60)` with `except asyncio.TimeoutError` per file.  
**Alternatives**: Keep 120s global `time.monotonic()` check (BUG 4: one slow file blocks all).  
**Rationale**: One slow/stuck file shouldn't prevent other results from being returned. 60s covers worst-case multi-page vision calls.

### Decision: Pipeline reorder (Markdown first, Vision last)

**Choice**: Split `target_files` into `markdown_files` (PDFs where MarkitDown returns rich text) and `vision_files` (images + PDF scans). Process markdown files first.  
**Alternatives**: Process in insertion order, parallel with `asyncio.gather`.  
**Rationale**: Markdown extraction is fast (~1-2s per file), vision is slow (~10-20s per file). Sequential processing yields markdown results quickly. Frontend gets partial results sooner.

## Data Flow

```
BEFORE (current):

Archivo → clsificar (extensión/MarkitDown)
  ├─ markitdown (>=50 chars)
  │   → extract_text_with_prompt [LLM call 1]
  │   → extract_fields_from_markdown [LLM call 2]  ← DOUBLE CALL (BUG 2)
  │
  └─ vision / vision_fallback (<50 chars)
      → pdf2image (1 page only) ← BUG 3
      → extract_text_with_prompt [LLM call 1]
      → extract_fields_from_markdown [LLM call 2]  ← DOUBLE CALL (BUG 2)

Pipeline: sequential for-loop + global 120s timeout ← BUG 1, BUG 4
All LLM calls BLOCK event loop ← BUG 1


AFTER:

target_files → split: markdown_files + vision_files

LOTE 1: markdown_files (for each, sequentially, 60s per file via asyncio.wait_for)
  MarkitdownExtractor → InvoiceExtractor.extract_fields_from_markdown() [1 LLM call, via asyncio.to_thread]

LOTE 2: vision_files (for each, sequentially, 60s per file)
  Image / pdf2image (ALL pages) → InvoiceExtractor.extract_fields_from_images() [1 LLM call, via asyncio.to_thread]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/services/preview_service.py` | Modify | B1: wrap sync calls in `asyncio.to_thread()`; B2: use unified vision agent; B3: convert all pages; B4: per-file timeout; pipeline reorder; remove `INVOICE_VISION_PROMPT` |
| `app/services/llm_extractor.py` | Modify | Add `extract_fields_from_images()` static method; update `extract_fields_from_markdown()` date format from YYYY-MM-DD to DD-MM-YYYY |

No changes to `llm_router.py` — existing `chat()` and `extract_text_with_prompt()` methods are reused as-is (called via `asyncio.to_thread`).

## Interfaces / Contracts

```python
@staticmethod
def extract_fields_from_images(
    images_base64: list[str],
    llm_router: LLMRouter
) -> dict:  # Same schema as extract_fields_from_markdown
```

Returns the same invoice JSON schema as `extract_fields_from_markdown()` — contracts unchanged.

## Open Questions

- None. All decisions are scoped and specified.

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Prompt change (DD-MM-YYYY) breaks existing data consumers | Low | Date format change is cosmetic — consumers parse variadic formats |
| Vision agent prompt quality | Med | Reuses proven JSON output patterns from existing extract_fields_from_markdown; 2x retry fallback |
| Thread safety with asyncio.to_thread | Low | LLMRouter creates fresh HTTP clients per call, no shared state |
