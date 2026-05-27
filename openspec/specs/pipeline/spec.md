# Delta for Pipeline

## ADDED Requirements

### Requirement: Concurrent File Processing

The pipeline MUST process all files concurrently using `asyncio.gather()` with `return_exceptions=True`.

The pipeline MUST limit concurrent file processing to N parallel calls using `asyncio.Semaphore(N)` where N defaults to 4.

A file timeout MUST NOT cancel processing of other files.

#### Scenario: All files complete in time

- GIVEN 8 files where each completes within 120s
- WHEN processing concurrently with Semaphore(4)
- THEN all 8 results MUST be returned successfully

#### Scenario: Timeout does not cancel siblings

- GIVEN 8 files where file 3 hangs indefinitely
- WHEN processing concurrently
- THEN file 3 MUST timeout after 120s and return as error
- AND remaining 7 files MUST complete normally

#### Scenario: Rate limit avoidance

- GIVEN 8 files ready for LLM processing
- WHEN Semaphore limits to 4 concurrent slots
- THEN at most 4 files SHALL enter LLM processing simultaneously
- AND remaining 4 SHALL wait until a slot frees

### Requirement: Response Format

The endpoint MUST return HTTP 200 with a complete JSON body.

The response MUST include these top-level fields: `facturas`, `total`, `errores`, `partial`.

The `partial` field MUST be `false` when all files processed.

The `partial` field MUST be `true` when the Semaphore concurrency limit prevents processing some files.

#### Scenario: Full success

- GIVEN all 8 files complete without errors
- WHEN the endpoint responds
- THEN `partial` MUST be `false`
- AND `total` MUST equal the count of `facturas`

#### Scenario: Partial due to concurrency limit

- GIVEN 8 files where 5 exceed the Semaphore limit
- WHEN the endpoint responds
- THEN `partial` MUST be `true`
- AND `errores` MUST list the skipped files

## MODIFIED Requirements

### Requirement: Per-file Timeout

Each file MUST have an independent timeout of 120 seconds via `asyncio.wait_for()`.
(Previously: 60 seconds)

#### Scenario: Timeout isolation with longer window

- GIVEN 3 files where file 2 hangs indefinitely
- WHEN processing all files concurrently
- THEN file 2 MUST timeout independently after 120 seconds
- AND files 1 and 3 SHALL complete normally
- AND the pipeline SHALL NOT abort other files

#### Scenario: All files complete in time

- GIVEN all files complete within 120 seconds each
- WHEN processing concurrently
- THEN all results MUST be returned successfully

## REMOVED Requirements

### Requirement: Processing Order

(Reason: Sequential ordering replaced by concurrent `asyncio.gather`. Within-batch order is non-deterministic.)
