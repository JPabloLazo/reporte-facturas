# Process Domain Specification

## Purpose

Robust error handling and explicit field mapping in the reconciliation endpoint's invoice processing loop.

## Requirements

### REQ-FMAP-001: Explicit FacturaDatos field mapping

The system SHALL map only valid FacturaDatos columns when constructing a FacturaDatos record from extraction results, instead of unpacking the full extraction dict.

#### Scenario: Extra keys excluded

- GIVEN extraction returns valid fields plus `{raw_response: "...", _retry: true, error: "invalid_json"}`
- WHEN the system creates a FacturaDatos record
- THEN non-column keys SHALL be excluded from the constructor

### REQ-ISOL-001: Per-factura error isolation

The system SHALL wrap each factura processing iteration in a try/except so that a single extraction failure does not crash the entire reconciliation.

#### Scenario: Partial extraction failure

- GIVEN 5 facturas where 1 extraction raises an exception
- WHEN the reconciliation processes all 5 facturas
- THEN 4 facturas SHALL be processed successfully
- AND the response SHALL include `facturas_con_error: 1`

#### Scenario: All extractions fail

- GIVEN 5 facturas where all extractions raise exceptions
- WHEN the reconciliation processes all 5 facturas
- THEN the response SHALL include `facturas_con_error: 5`
- AND no unhandled exception SHALL propagate

### REQ-ISOL-002: Error count in response

The system SHALL include a `facturas_con_error` field in the response with the count of failed extractions.

#### Scenario: Error reporting

- GIVEN reconciliation completes with N failed extractions
- WHEN the endpoint returns the response
- THEN the response SHALL contain `facturas_con_error` equal to N
