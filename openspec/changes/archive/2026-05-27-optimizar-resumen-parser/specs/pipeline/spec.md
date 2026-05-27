# Delta for Pipeline

## ADDED Requirements

### Requirement: Non-Blocking Image Conversion

The upload endpoint MUST NOT block the event loop during PDF-to-image conversion. `convert_from_path` MUST be wrapped in `asyncio.to_thread()`.

#### Scenario: Concurrent uploads

- GIVEN 2 concurrent resumen uploads
- WHEN both trigger `convert_from_path`
- THEN both SHALL execute without blocking the event loop

### Requirement: Non-Blocking LLM Extraction

The upload endpoint MUST NOT block the event loop during LLM extraction fallback. The call MUST be wrapped in `asyncio.to_thread()`.

#### Scenario: Upload with LLM call

- GIVEN a resumen triggering the LLM fallback
- WHEN the LLM call is active
- THEN the event loop SHALL remain responsive to other requests

### Requirement: Upload Error Resets UI

On extraction error, the frontend MUST reset the upload UI, unblocking the drop zone and file input.

#### Scenario: Upload error recovery

- GIVEN a user uploads a resumen that fails extraction
- WHEN the error response is received
- THEN the drop zone MUST be re-enabled
- AND the file input MUST be unblocked

### Requirement: Multi-Page Resumen Strategy

The resumen parser MUST process page 1 separately for metadata (card type, period, totals).

Transaction pages (page 2+) MUST be processed in parallel via `asyncio.gather` limited to 3 concurrent calls via `asyncio.Semaphore(3)`.

Merged results MUST maintain chronological order by transaction date.

#### Scenario: Parallel page processing

- GIVEN a 10-page resumen PDF
- WHEN page 1 yields metadata and 9 transaction pages are dispatched
- THEN pages 2–10 MUST run with at most 3 concurrent LLM calls
- AND results MUST be merged chronologically

#### Scenario: Single-page resumen

- GIVEN a resumen PDF with only 1 page
- WHEN processed
- THEN all data MUST come from that single page
- AND no parallel processing SHALL occur

### Requirement: PDF Caching

Resumen processing results SHOULD be cached by content hash to avoid reprocessing identical files.

The cache key MUST be `hashlib.md5(pdf_bytes)`.

#### Scenario: Cache hit

- GIVEN a previously uploaded resumen PDF
- WHEN uploaded again
- THEN cached results MUST be returned without re-extraction

### Requirement: Optimized JPEG Quality

PDF-to-image conversion for resúmenes MUST use JPEG quality=60.

#### Scenario: Lower quality conversion

- GIVEN a resumen PDF
- WHEN converted to JPEG images
- THEN the quality parameter MUST be 60
