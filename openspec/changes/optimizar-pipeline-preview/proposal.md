# Proposal: Optimizar Pipeline Preview

## Intent

Fix 4 bugs in the preview pipeline that cause blocked event loops, double LLM calls per file, single-page PDF handling, and inadequate timeouts. Reduce latency 2x by eliminating redundant LLM calls.

## Scope

### In Scope
- B1: Wrap sync LLM calls with `asyncio.to_thread()` in `preview_service.py`
- B2: Create **Vision Agent** (single LLM call image→JSON) + **Markdown Agent** (text→JSON), remove double-call pattern
- B3: Convert ALL PDF pages (not just page 1) via `convert_from_bytes`
- B4: Per-file `asyncio.wait_for()` timeout instead of 120s global
- Reorder pipeline: process Markdown files first (fast/cheap), images last (slow/expensive)

### Out of Scope
- Background task queue or WebSocket streaming
- Adding test coverage (deferred to separate change)
- UI changes

## Approach

1. **B1**: Wrap `llm_router.extract_text_with_prompt()` and `InvoiceExtractor.extract_fields_from_markdown()` in `await asyncio.to_thread()` in `preview_service.py`
2. **B2**: Add `extract_with_vision_agent()` and `extract_with_markdown_agent()` methods to `LLMRouter`/`InvoiceExtractor`. Vision Agent: receives PIL Image → returns JSON directly (1 call). Markdown Agent: receives text → returns JSON directly (replaces current 2-call flow)
3. **B3**: Change `convert_from_bytes(pdf_bytes, first_page=1, last_page=1)` → `first_page=1, last_page=pdf_page_count`
4. **B4**: Replace 120s global timeout with `asyncio.wait_for(invoice_task, timeout=30)` per invoice
5. Reorder: sort files — Markdown-suitable PDFs first, images/scan-PDFs second; yield partial results as they complete

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/services/preview_service.py` | Modified | B1, B3, B4, pipeline reorder |
| `app/services/llm_extractor.py` | Modified | B2: add Vision Agent + Markdown Agent methods |
| `app/services/llm_router.py` | Modified | B2: add agent prompt methods |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Prompt changes break extraction quality | Med | Keep old prompts as fallback, test with varied invoice types |
| Pipeline reorder changes response shape | Low | Return `extraction_method` field per invoice so frontend is transparent |
| `asyncio.to_thread()` thread-safety in httpx | Low | `httpx.Client` is already synchronous and not shared across calls |

## Rollback Plan

`git checkout` all changed files. The old pipeline remains fully functional — changes are purely performance/stability optimizations with no schema or API contract changes.

## Dependencies

- Python stdlib `asyncio` (no new packages)

## Success Criteria

- [ ] B1: Sync LLM calls no longer block the event loop (verified via asyncio debug logging)
- [ ] B2: Each file makes exactly 1 LLM call (verified via call counting); extracted JSON quality matches or exceeds current 2-call output
- [ ] B3: PDFs with 3+ pages return complete data including totals from last page
- [ ] B4: One slow file (timeout) does NOT block other files from completing
