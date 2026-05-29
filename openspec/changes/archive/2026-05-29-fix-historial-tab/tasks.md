# Tasks: fix-historial-tab

## Phase 1: Foundation

- [ ] 1.1 Read `app/routers/reports.py` to understand existing patterns and imports.
- [ ] 1.2 Read `app/templates/index.html` to locate Historial stub markup.
- [ ] 1.3 Read `app/static/js/main.js` to understand tab activation and existing helpers.

## Phase 2: Backend — List Endpoint

- [ ] 2.1 Add `GET /api/reports/historial` to `app/routers/reports.py` with offset/limit query params.
- [ ] 2.2 Implement aggregated SQL query using `func.count` + `case` for `total_transacciones`, `matched`, and `unmatched`.
- [ ] 2.3 Return JSON shape `{"items": [...], "total": N}`.

## Phase 3: Backend — Delete Endpoint

- [ ] 3.1 Add `DELETE /api/reports/historial/{resumen_id}` to `app/routers/reports.py`.
- [ ] 3.2 Return `{"status": "deleted"}` on success; raise `HTTPException(404)` if resumen missing.
- [ ] 3.3 Confirm DB CASCADE removes dependent `transaccion`, `conciliacion`, and `factura` rows.

## Phase 4: Frontend — Historial Tab Markup

- [ ] 4.1 Replace Historial stub in `app/templates/index.html` with table markup (`<table>`, `<thead>`, `<tbody id="historial-tbody">`).
- [ ] 4.2 Add loading spinner element with text "Cargando historial...".
- [ ] 4.3 Add empty-state placeholder element with text "No hay procesamientos previos".

## Phase 5: Frontend — Fetch and Render

- [ ] 5.1 Add `initHistorial()` in `app/static/js/main.js` triggered on Historial tab activation.
- [ ] 5.2 Fetch `GET /api/reports/historial?offset=0&limit=20`, toggle spinner visibility.
- [ ] 5.3 Render rows into `#historial-tbody` with columns: periodo, tipo, archivo_nombre, fecha_creacion, total_transacciones, matched_count, unmatched_count.
- [ ] 5.4 Show empty-state when `items` array is empty; hide it when rows exist.

## Phase 6: Frontend — Row Actions

- [ ] 6.1 Wire "Ver detalle" button to load resumen data into Procesar tab and activate it.
- [ ] 6.2 Wire "Descargar Excel" button to call existing Excel download endpoint for the row's resumen ID.
- [ ] 6.3 Wire "Descargar PDF" button to call existing PDF download endpoint for the row's resumen ID.
- [ ] 6.4 Wire "Eliminar" button to show `confirm("¿Eliminar este procesamiento?")`, then call `DELETE /api/reports/historial/{id}`.
- [ ] 6.5 On successful delete, refresh the historial list and show `alert("Eliminado correctamente")`.

## Phase 7: Testing

- [ ] 7.1 Run backend integration tests for `GET /historial` pagination and response shape.
- [ ] 7.2 Run backend integration tests for `DELETE /historial/{id}` cascade and 404 cases.
- [ ] 7.3 Manual browser verification: open Historial tab, confirm rows render, test delete flow.
