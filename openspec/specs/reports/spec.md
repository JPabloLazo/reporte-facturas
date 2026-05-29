# Delta for Reports

## ADDED Requirements

### Requirement: List Historical Resúmenes
The system MUST expose `GET /api/reports/historial` that returns a paginated list of Resumen rows with aggregated counts.

#### Scenario: Happy path — list with data
- GIVEN at least one Resumen exists in the database
- WHEN the frontend sends `GET /api/reports/historial?page=1&limit=20`
- THEN the response SHALL contain `items` with fields: `id`, `periodo`, `tipo`, `archivo_nombre`, `fecha_creacion`, `total_transacciones`, `matched_count`, `unmatched_count`
- AND `total` SHALL reflect the total number of resúmenes

#### Scenario: Empty historial
- GIVEN no Resumen rows exist
- WHEN the frontend requests the endpoint
- THEN the response SHALL return `items` as an empty array and `total` as 0

### Requirement: Delete a Resumen
The system MUST expose `DELETE /api/reports/historial/{resumen_id}` that removes a Resumen and all dependent records.

#### Scenario: Successful deletion
- GIVEN a Resumen with related Transaccion, Conciliacion, and Factura rows exists
- WHEN the frontend sends `DELETE /api/reports/historial/{resumen_id}`
- THEN the Resumen and all its dependent records SHALL be removed
- AND the response SHALL return `{"success": true}`

#### Scenario: Delete non-existent resumen
- GIVEN the provided `resumen_id` does not exist
- WHEN the frontend sends the DELETE request
- THEN the system SHALL return HTTP 404 with `{"detail": "Resumen no encontrado"}`

### Requirement: Lazy-Load Table on Tab Activation
The Historial tab MUST fetch and render data only when it becomes the active tab.

#### Scenario: Tab opened
- GIVEN the user clicks the Historial tab
- WHEN the tab becomes visible
- THEN `initHistorial()` SHALL trigger a fetch to `GET /api/reports/historial`
- AND a loading spinner with text "Cargando historial..." SHALL be displayed
- AND the spinner SHALL be removed once data arrives or an error occurs

#### Scenario: Empty state
- GIVEN the Historial tab is active and the API returns an empty list
- WHEN the spinner is removed
- THEN an empty-state message "No hay procesamientos previos" SHALL be displayed

### Requirement: Render Historical Rows (Clickable)
The system MUST render each Resumen as a fully clickable table row without inline action buttons.

#### Scenario: Rows rendered without action column
- GIVEN the API returns historial items
- WHEN the data is rendered
- THEN each row SHALL display: periodo, tipo, archivo_nombre, fecha_creacion, total_transacciones, matched_count, unmatched_count
- AND no row SHALL contain a `.historial-btn-detail`, `.historial-btn-excel`, `.historial-btn-pdf`, or `.historial-btn-delete` element
- AND each row SHALL have `cursor-pointer` style
- AND clicking anywhere on the row SHALL call `showHistorialDetailModal(item.id)`

### Requirement: Row Actions (Modal-Based)
Clicking a historial row SHALL open a detail modal instead of switching tabs.

#### Scenario: Row click opens detail modal
- GIVEN a historial table with one or more items
- WHEN the user clicks anywhere on a row (not a child button/link)
- THEN the system calls showHistorialDetailModal with the item's resumen ID
- AND no tab switch or window._resumenId mutation occurs

### Requirement: Historial Detail Modal Component
The system MUST render a modal overlay (z-50) triggered by row click, with header (periodo, tipo, archivo_nombre), read-only transaction table, Download Excel, Download PDF, Delete, and close buttons.

#### Scenario: Modal displays full detail on row click
- GIVEN the user clicked a historial row
- WHEN showHistorialDetailModal(resumenId) fetches GET /api/reports/{resumenId}
- THEN the modal header shows periodo, tipo, and archivo_nombre
- AND the transaction table renders all rows from data.transacciones
- AND Excel button links to /api/reports/{resumenId}/excel?filter=all
- AND PDF button links to /api/reports/{resumenId}/transactions/pdf
- AND Delete button calls deleteHistorialItem(resumenId)

#### Scenario: Close modal on × or backdrop click
- GIVEN the historial detail modal is visible
- WHEN the user clicks the × button or the dark backdrop overlay
- THEN the modal adds the "hidden" class and is no longer visible

#### Scenario: Delete inside modal removes item and closes modal
- GIVEN the historial detail modal is visible with a loaded item
- WHEN the user clicks Delete and confirms
- THEN the system calls deleteHistorialItem(resumenId)
- AND the modal is hidden
- AND initHistorial() refreshes the table

### Requirement: showHistorialDetailModal Function
The system MUST add a new function `showHistorialDetailModal(resumenId)` that fetches GET /api/reports/{resumenId} and populates the modal.

#### Scenario: Modal loads and displays data
- GIVEN a valid resumenId
- WHEN showHistorialDetailModal(resumenId) is called
- THEN a GET /api/reports/{resumenId} request is made
- AND on success the modal header shows periodo, tipo, archivo_nombre
- AND the transaction table is populated
- AND the modal "hidden" class is removed

#### Scenario: API error in showHistorialDetailModal
- GIVEN an invalid resumenId or network failure
- WHEN showHistorialDetailModal(resumenId) is called
- THEN the modal remains hidden
- AND showToast is called with the error message

### Requirement: Existing Schema Sufficiency
The system MUST use the existing tables without modification.

#### Scenario: Data already persisted
- GIVEN the existing tables `resumen`, `transaccion`, `conciliacion`, and `factura`
- WHEN a new procesamiento is uploaded
- THEN records are already created in these tables
- AND the Historial feature SHALL read from and delete from these existing tables only

### Requirement: Conciliacion Data in Transaction Response
The system MUST return conciliacion data alongside transacciones in the GET /api/reports/{id} response.

Each transaccion MUST include an optional `conciliacion` object with: `estado`, `confianza`, `metodo`, and nested `factura` object when estado=MATCHED.

The factura object MUST include: `drive_file_name`, `monto_total`, `subtotal`, `tipo_factura`, `fecha`, `vencimiento`, `emisor`, `cuit_emisor`, `numero_factura`.

When a transaccion has NO conciliacion record at all, the `conciliacion` field MUST be null.

When a conciliacion exists with estado=UNMATCHED (factura_id is null), the `conciliacion` object MUST include `estado`, `confianza`, `metodo` but `factura` MUST be null.

#### Scenario: MATCHED with factura
- GIVEN a transaccion with a Conciliacion where estado=MATCHED and factura_id points to an existing Factura with FacturaDatos
- WHEN GET /api/reports/{id} is called
- THEN the response includes `conciliacion.estado` = "MATCHED", `conciliacion.factura.drive_file_name` = the factura's filename, `conciliacion.factura.monto_total` = the factura_datos monto

#### Scenario: UNMATCHED without factura
- GIVEN a transaccion with a Conciliacion where estado=UNMATCHED and factura_id is null
- WHEN GET /api/reports/{id} is called
- THEN the response includes `conciliacion.estado` = "UNMATCHED" and `conciliacion.factura` = null

#### Scenario: No conciliacion record
- GIVEN a transaccion with NO Conciliacion record at all
- WHEN GET /api/reports/{id} is called
- THEN the response includes `conciliacion` = null for that transaccion
