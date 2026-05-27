# Count — LLM Transaction Counting Function

## Purpose

A lightweight LLM call that counts only real transactions from page images, providing the expected count for integrity validation.

## Requirements

### Requirement: REQ-COUNT-001 — Transaction definition and prompt

`count_transactions()` SHALL use a card-type-specific prompt that instructs the LLM to count ONLY real transactions.

A real transaction is: any purchase, payment, charge, or installment with a date and description.

Do NOT count: previous balances, totals, subtotals, headers, footers, page numbers, fees, or "gracias por su pago" messages.

#### Scenario: Real transaction types

- GIVEN a resumen page with 12 purchases and 1 "TOTAL" line
- WHEN `count_transactions` is called
- THEN it SHALL return 12
- AND SHALL NOT count the TOTAL line

#### Scenario: Elements to exclude

- GIVEN a resumen page with 5 purchases, 1 previous balance, 1 total, and 2 header lines
- WHEN `count_transactions` is called
- THEN it SHALL return 5
- AND SHALL NOT count balance, total, headers, or footers

### Requirement: REQ-COUNT-002 — Response format

The prompt SHALL request output as a single integer only.

#### Scenario: Valid numeric response

- GIVEN the LLM responds with "37"
- THEN `count_transactions` SHALL return integer 37

#### Scenario: Non-numeric response

- GIVEN the LLM responds with "there are thirty-seven transactions"
- THEN `count_transactions` SHALL return None

#### Scenario: API error

- GIVEN the LLM API call raises an exception
- THEN `count_transactions` SHALL return None
