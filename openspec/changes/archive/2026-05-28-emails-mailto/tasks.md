# Tasks: emails-mailto

## Phase 1: Backend — Email Generator

- [x] 1.1 Refactor `EmailGenerator.generate_email_content()` → `generate_emails()` accepting `transacciones_unmatched`, `tarjetas`, `tipo_resumen`, `periodo`, `llm_router`
- [x] 1.2 Write LLM prompt to group unmatched by cardholder, return JSON array with `recipient_email`, `recipient_name`, `subject`, `body_html`, `body_text`
- [x] 1.3 Add fallback static template when LLM fails or returns invalid JSON

## Phase 2: Backend — Endpoints

- [x] 2.1 Add `POST /{resumen_id}/email/preview` in `app/routers/reports.py` — query unmatched + tarjetas, call `generate_emails()`, return `{emails: [...]}`
- [x] 2.2 Remove `POST /{resumen_id}/email` from `app/routers/reports.py`
- [x] 2.3 Delete `app/services/email_sender.py`

## Phase 3: Backend — SMTP Cleanup

- [x] 3.1 Remove `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `email_from`, `email_responsable` from `app/config.py` Settings
- [x] 3.2 Remove SMTP fields from PUT mapping and GET response in `app/routers/config.py`

## Phase 4: Frontend

- [x] 4.1 Remove SMTP section (host/port/user/pass/responsable) from `app/templates/config.html`
- [x] 4.2 Remove SMTP from `initConfig()`/`loadConfig()` in `app/static/js/main.js`
- [x] 4.3 Add email preview modal HTML in `app/templates/base.html` (editable to/subject/body per draft, Enviar/Eliminar/Cancelar)
- [x] 4.4 Add `initEmailModal()`, `fetchEmailPreview()`, `openMailto()` in `app/static/js/main.js`
- [x] 4.5 Add modal styles in `app/static/css/styles.css`

## Phase 5: Verification

- [ ] 5.1 `curl POST /api/reports/{id}/email/preview` — verify JSON has real `recipient_email` from `tarjetas_usuarios`
- [ ] 5.2 Click preview on report page — verify modal shows editable drafts with to/subject/body per cardholder
- [ ] 5.3 Click Enviar — verify `mailto:` opens with correct pre-filled data
- [ ] 5.4 Open Config page — verify no SMTP section renders
- [ ] 5.5 `GET /api/config` — verify no `smtp_*` fields in response
