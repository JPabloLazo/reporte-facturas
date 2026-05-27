# Invoice Extraction Specification

## Purpose

Unified single-call LLM agents for invoice field extraction from Vision (image) and Markdown (text) sources, with standardized DD-MM-YYYY date format.

## Requirements

### Requirement: Unified Vision Agent

The Vision Agent MUST extract all invoice fields from one or more images in a single LLM call returning JSON directly.

#### Scenario: Single image invoice

- GIVEN a single invoice page image
- WHEN the Vision Agent is invoked
- THEN it MUST make exactly 1 LLM call
- AND the response MUST be valid JSON with fields: invoice_number, date, supplier, amounts, total

#### Scenario: Multi-page PDF as images

- GIVEN a PDF with 3 pages converted to images
- WHEN the Vision Agent is invoked with all 3 images
- THEN it MUST extract fields across all images in 1 LLM call
- AND the response MUST include data from the last page

#### Scenario: Extraction failure

- GIVEN an unreadable image
- WHEN the Vision Agent fails to extract valid JSON
- THEN the agent MUST return an error indicator
- AND the pipeline SHALL continue processing remaining files

### Requirement: Unified Markdown Agent

The Markdown Agent MUST extract invoice fields from markdown text in a single LLM call returning JSON directly.

#### Scenario: Markdown text extraction

- GIVEN markdown text from a text-based PDF
- WHEN the Markdown Agent is invoked
- THEN it MUST make exactly 1 LLM call
- AND the response MUST be valid JSON with all invoice fields

### Requirement: Date Format — DD-MM-YYYY

Both agents MUST return dates in DD-MM-YYYY format in their prompts and responses.

#### Scenario: Date extraction

- GIVEN an invoice with a date of "January 15, 2025"
- WHEN either agent extracts the date
- THEN it MUST return "15-01-2025"

### Requirement: Single Call per File

Each file SHOULD make exactly 1 LLM call to the appropriate agent (Vision or Markdown), replacing the current 2-call pattern.

#### Scenario: Pipeline routing

- GIVEN a file determined to be Markdown-suitable
- WHEN routed through the pipeline
- THEN it MUST go to the Markdown Agent only
- AND no Vision Agent call SHALL be made
