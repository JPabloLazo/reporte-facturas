# Tasks: Historial Modal — Conciliaciones

## Phase 1: Foundation

- [x] 1.1 Read `app/models.py:72-130` — understand Conciliacion, Factura, FacturaDatos relationships
- [x] 1.2 Read `app/routers/reports.py:339-374` — current `get_resumen` query
- [x] 1.3 Read `app/static/js/main.js:776-798` — current `renderTransactionRows(tbodyId, data)` function
- [x] 1.4 Read `app/static/js/main.js:1613-1659` — current `showHistorialDetailModal(resumenId)` function
- [x] 1.5 Read `app/templates/index.html:385-398` — historial modal table header and tbody

## Phase 2: Backend — extend GET /api/reports/{id} with conciliacion joins

- [x] 2.1 Replace the `select(Transaccion)` query with 4-table LEFT OUTER JOIN
- [x] 2.2 Extend response dict with estado, confianza, metodo, factura (nested when MATCHED)

## Phase 3: HTML — add 4 header columns

- [x] 3.1 Add 4 `<th>` after Cuota: Estado, Factura, Monto factura, Confianza

## Phase 4: JS — extend renderTransactionRows with includeConciliacion flag

- [x] 4.1 Add 3rd parameter `includeConciliacion = false` to signature
- [x] 4.2 When true, append 4 extra `<td>` cells: Estado badge, Factura button, Monto factura currency, Confianza %
- [x] 4.3 Implement badge logic (green MATCHED / red UNMATCHED / grey null)

## Phase 5: JS — inline expand/collapse for factura details

- [x] 5.1 Hidden detail row with colspan=9 after each MATCHED row
- [x] 5.2 Wire click handler on `.factura-toggle` to toggle next-sibling `.factura-detail-row`
- [x] 5.3 Guard against double-click (handled by class toggle idempotency)

## Phase 6: JS — wire showHistorialDetailModal to pass includeConciliacion=true

- [x] 6.1 Changed to `renderTransactionRows('historial-modal-tbody', data, true)`

## Phase 7: Verify — manual checklist

- [ ] 7.1 Load a report with MATCHED conciliación → green "Match" badge, clickable factura name, expand/collapse
- [ ] 7.2 Load a report with UNMATCHED conciliación → red "Sin factura" badge
- [ ] 7.3 Load a report with no conciliación records → grey "Sin procesar" badge
- [ ] 7.4 Verify existing `showTransactionsTable` caller still works
