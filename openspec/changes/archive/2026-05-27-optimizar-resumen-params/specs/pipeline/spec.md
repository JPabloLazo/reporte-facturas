# Delta for Pipeline

## ADDED Requirements

### Requirement: Image Conversion DPI

PDF-to-image conversion SHALL use DPI=100 for resumen processing.

#### Scenario: Standard conversion

- GIVEN a resumen PDF with 10pt+ fonts
- WHEN converted to images via `convert_from_path`
- THEN the DPI parameter MUST be 100

#### Scenario: Small print safety

- GIVEN a resumen PDF with very small print (<10pt)
- WHEN converted at DPI=100
- THEN the pipeline SHALL still complete without error
- AND extracted fields MAY have lower accuracy

### Requirement: Maximum PDF Pages

The pipeline SHALL limit `convert_from_path` to a maximum of 15 pages (`max_pages=15`).

#### Scenario: Within page limit

- GIVEN a 6-page AMEX resumen
- WHEN converted via `convert_from_path` with max_pages=15
- THEN all 6 pages SHALL be returned

#### Scenario: Exceeds page limit

- GIVEN a resumen exceeding 15 pages
- WHEN converted with max_pages=15
- THEN only the first 15 pages SHALL be processed
- AND a warning SHALL be logged

## MODIFIED Requirements

### Requirement: Optimized JPEG Quality

PDF-to-image conversion MUST use JPEG quality=50.
(Previously: quality=60)

#### Scenario: Lower quality conversion

- GIVEN a resumen PDF
- WHEN converted to JPEG images
- THEN the quality parameter MUST be 50

### Requirement: Multi-Page Resumen Strategy

Each LLM call SHALL process exactly 1 transaction page (batch_size=1).
(Previously: 2 pages per call)

Concurrent LLM calls SHALL remain limited via Semaphore.

#### Scenario: One page per call

- GIVEN a 10-page resumen PDF
- WHEN transaction pages are dispatched to LLM
- THEN each LLM call SHALL receive exactly 1 page
- AND results SHALL be merged chronologically

#### Scenario: Single-page resumen

- GIVEN a resumen PDF with only 1 page
- WHEN processed
- THEN no LLM batch SHALL be dispatched for transaction pages
