# Email Specification

## Purpose

Replace SMTP with `mailto:` links. LLM generates email drafts grouped by cardholder, user edits in modal, confirm opens native email client.

## Added Requirements

### REQ-PREVIEW-001: Generar preview de emails

When user requests preview, system MUST generate drafts via LLM grouped by unmatched transactions per card.

#### Scenario: LLM generates drafts

- GIVEN a processed report with UNMATCHED transactions and registered cards
- WHEN user clicks "Previsualizar emails"
- THEN LLM MUST return drafts with: `recipient_email`, `recipient_name`, `subject`, `body_html`
- AND LLM MUST NOT invent recipients — only `TarjetaUsuario` emails
- AND cards without registered email SHALL be excluded

### REQ-PREVIEW-002: Agrupación por titular

System MUST generate ONE email per cardholder, NOT one per transaction.

#### Scenario: Same cardholder, multiple cards

- GIVEN unmatched transactions from two cards with the SAME titular email
- WHEN drafts are generated
- THEN response MUST contain exactly ONE draft for that cardholder referencing all transactions

#### Scenario: Different cardholders

- GIVEN unmatched transactions from cards with DIFFERENT titulares
- WHEN drafts are generated
- THEN response MUST contain one draft per cardholder
- AND drafts MUST NOT be merged

### REQ-PREVIEW-003: Modal editable

Drafts MUST display in an editable modal with confirm/cancel options.

#### Scenario: Preview shown in modal

- GIVEN drafts are returned by LLM
- WHEN modal opens
- THEN each draft MUST show recipient, subject, body
- AND user SHALL edit recipient, subject, body per draft
- AND user SHALL remove individual drafts
- AND "Confirmar" and "Cancelar" buttons SHALL be present

#### Scenario: No drafts

- GIVEN all transactions MATCHED or no card emails
- WHEN user clicks "Previsualizar emails"
- THEN system MUST show "No hay emails para generar"
- AND modal SHALL NOT display drafts

### REQ-SEND-001: Envío via mailto

Confirm MUST open `mailto:` links per draft in native client.

#### Scenario: Confirm opens mailto

- GIVEN user edited drafts in modal
- WHEN user clicks "Confirmar"
- THEN ONE `mailto:` SHALL open per draft with `to`, `subject`, `body` pre-filled
- AND body SHALL include inline HTML table (no Excel attachment)
- AND user SHALL NOT leave report page

#### Scenario: Cancel

- GIVEN modal is open with drafts
- WHEN user clicks "Cancelar"
- THEN modal SHALL close
- AND no email client SHALL open
- AND drafts SHALL be discarded

## Modified Requirements

### REQ-SMTP-001: Eliminar SMTP de UI

Config page MUST NOT render SMTP fields. (Previously: had smtp_host, smtp_port, smtp_user, smtp_password, email_responsable fields.)

#### Scenario: No SMTP fields

- GIVEN user opens Configuración page
- WHEN inspecting the form
- THEN no SMTP section SHALL exist
- AND no smtp_host/port/user/password/responsable fields SHALL render

### REQ-SMTP-002: Eliminar SMTP de backend

Config endpoints MUST NOT expose/accept SMTP fields. (Previously: GET returned and PUT accepted smtp_* and responsable_email.)

#### Scenario: GET config excludes SMTP

- GIVEN user loads configuration
- WHEN GET /api/config is called
- THEN response MUST NOT contain smtp_host, smtp_port, smtp_user, smtp_password, responsable_email

#### Scenario: PUT config ignores SMTP

- GIVEN payload includes smtp_* or responsable_email
- WHEN PUT /api/config is called
- THEN server MUST ignore those fields

### REQ-SMTP-003: Eliminar SMTP de Settings

`Settings` in `app/config.py` MUST NOT have SMTP fields. (Previously: smtp_host/port/user/password/from/responsable.)

#### Scenario: No SMTP in Settings

- GIVEN application starts
- WHEN `app/config.py` loads
- THEN Settings SHALL NOT contain smtp_host, smtp_port, smtp_user, smtp_password, email_from, email_responsable
- AND `app/services/email_sender.py` SHALL be removed
