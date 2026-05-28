# LLM Extractor Domain Specification

## Purpose

Guarantee that the `extract_fields_from_markdown` method always has a defined `response` variable before accessing it in error handlers, preventing `UnboundLocalError`.

## Requirements

### REQ-RESP-001: Response variable initialization

The system SHALL initialize `response = ""` before the first extraction try block so that the error handler never accesses an unbound variable.

#### Scenario: Both attempts fail

- GIVEN the first LLM call raises an exception before assigning `response`
- AND the second LLM call also raises an exception before assigning `response`
- WHEN `extract_fields_from_markdown` handles the exceptions
- THEN the method SHALL return `{"error": "invalid_json", ...}` without raising `UnboundLocalError`
- AND `raw` in the response SHALL be `""`
