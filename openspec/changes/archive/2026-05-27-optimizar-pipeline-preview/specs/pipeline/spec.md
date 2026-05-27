# Pipeline Orchestration Specification

## Purpose

Concurrent file processing pipeline with non-blocking LLM execution, multi-page PDF conversion, per-file timeouts, and deterministic processing order.

## Requirements

### Requirement: Non-blocking LLM Execution

The pipeline MUST execute synchronous LLM calls via `asyncio.to_thread()` to prevent blocking the async event loop.

#### Scenario: Sync call wrapped in thread

- GIVEN the pipeline is processing an invoice file
- WHEN a synchronous LLM method is invoked
- THEN the call MUST be wrapped in `await asyncio.to_thread()`
- AND the event loop SHALL remain responsive to other tasks

### Requirement: Multi-page PDF Conversion

The pipeline SHALL convert ALL pages of a PDF, not only the first page.

#### Scenario: Multi-page PDF processed

- GIVEN a PDF with 3+ pages
- WHEN `convert_from_bytes()` is called
- THEN ALL pages SHALL be converted to images
- AND each image SHALL be passed to the Vision agent

#### Scenario: Single-page PDF

- GIVEN a single-page PDF
- WHEN converted
- THEN behavior MUST be identical to current single-page handling

### Requirement: Per-file Timeout

Each file MUST have an independent timeout of 60 seconds via `asyncio.wait_for()`.

#### Scenario: File timeout isolation

- GIVEN 3 files where file 2 hangs indefinitely
- WHEN processing all files concurrently
- THEN file 2 MUST timeout independently after 60 seconds
- AND files 1 and 3 SHALL complete normally
- AND the pipeline SHALL NOT abort other files

#### Scenario: All files complete in time

- GIVEN all files complete within 60 seconds each
- WHEN processing concurrently
- THEN all results MUST be returned successfully

### Requirement: Processing Order

The pipeline SHOULD process Markdown-suitable PDFs first, then Vision-dependent files (scanned PDFs, images).

#### Scenario: Mixed file types

- GIVEN 3 files: 1 Markdown-suitable PDF, 2 scanned PDFs
- WHEN the pipeline starts
- THEN the Markdown-suitable file SHOULD be queued first
- AND results MAY be yielded as they complete
