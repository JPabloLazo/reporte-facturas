# Tasks: Redesign Historial "Ver detalle" to Modal

## Phase 1: Foundation — Read & Confirm Context

- [x] 1.1 Read `app/templates/index.html` — locate the email-modal block, modal zone, Acciones column
- [x] 1.2 Read `app/static/js/main.js` — find loadResumenDetail, showTransactionsTable, initHistorial, deleteHistorialItem, window._resumenId usage

## Phase 2: HTML — index.html

- [x] 2.1 Remove Acciones `<th>` from thead and Acciones `<td>` from tbody row template
- [x] 2.2 Add `cursor-pointer` class to historial `<tr>`
- [x] 2.3 Insert `#historial-modal` markup in the modal zone (backdrop, header, error div, body table, empty-state, footer with buttons)

## Phase 3: JS Refactor — Row Clickable, No Inline Buttons

- [x] 3.1 In `initHistorial`, remove 4 inline action buttons; attach single onclick per row calling showHistorialDetailModal(item.id)

## Phase 4: JS New — showHistorialDetailModal

- [x] 4.1 Add showHistorialDetailModal(resumenId) — reset modal, fetch, populate, error handling
- [x] 4.2 Extract shared helper renderTransactionRows(tbodyId, transacciones) from showTransactionsTable

## Phase 5: JS Modals — Wire Buttons Inside Modal

- [x] 5.1 Wire Download Excel: /api/reports/{data.resumen_id}/excel?filter=all
- [x] 5.2 Wire Download PDF: /api/reports/{data.resumen_id}/transactions/pdf
- [x] 5.3 Wire Delete: close modal → deleteHistorialItem → initHistorial refresh
- [x] 5.4 Wire close (×) and backdrop click to closeHistorialModal
- [x] 5.5 Add closeHistorialModal() — adds "hidden" class

## Phase 6: JS Clean — Verify No Side Effects

- [x] 6.1 Verify loadResumenDetail is removed — no window._resumenId write, no tab switch
- [x] 6.2 Verify showHistorialDetailModal uses data.resumen_id, never window._resumenId

## Phase 7: Manual Verification Checklist

- [ ] 7.1 Open historial — no Acciones column; rows have pointer cursor
- [ ] 7.2 Click a row — modal opens with correct periodo/tipo/archivo in header
- [ ] 7.3 Transaction table inside modal renders all columns
- [ ] 7.4 Download Excel button triggers correct URL
- [ ] 7.5 Download PDF button triggers correct URL
- [ ] 7.6 Delete inside modal removes item and refreshes table
- [ ] 7.7 Close via × and backdrop click — modal hides
- [ ] 7.8 Active tab stays "Historial" after row click
- [ ] 7.9 Procesar tab showTransactionsTable still works independently
