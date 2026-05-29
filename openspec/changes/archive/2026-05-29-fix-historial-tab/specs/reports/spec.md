# Backend / Reports Specification

## Purpose
Define the API contract for listing and deleting historical procesamientos in the Historial tab.

## Requirements

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

---

# Frontend / UI Specification

## Purpose
Define the behavior of the Historial tab in the single-page application.

## Requirements

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

### Requirement: Render Historical Rows
The system MUST render each Resumen as a table row with action buttons.

#### Scenario: Rows rendered
- GIVEN the API returns historial items
- WHEN the data is rendered
- THEN each row SHALL display: periodo, tipo, archivo_nombre, fecha_creacion, total_transacciones, matched_count, unmatched_count
- AND each row SHALL include buttons for: Ver detalle, Descargar Excel, Descargar PDF, Eliminar

### Requirement: Row Actions
Clicking row action buttons SHALL trigger the corresponding behavior.

#### Scenario: View detail
- GIVEN a row has a "Ver detalle" button
- WHEN the user clicks it
- THEN the corresponding Resumen data SHALL be loaded into the Procesar tab
- AND the Procesar tab SHALL become active

#### Scenario: Delete with confirmation
- GIVEN a row has an "Eliminar" button
- WHEN the user clicks it
- THEN a browser confirmation dialog SHALL appear with the text "¿Eliminar este procesamiento?"
- AND upon confirmation the system SHALL send `DELETE /api/reports/historial/{id}`
- AND on success the list SHALL refresh and a toast "Eliminado correctamente" SHALL appear

---

# Data Model Specification

## Purpose
Confirm that no schema changes are required for the Historial tab feature.

## Requirements

### Requirement: Existing Schema Sufficiency
The system MUST use the existing tables without modification.

#### Scenario: Data already persisted
- GIVEN the existing tables `resumen`, `transaccion`, `conciliacion`, and `factura`
- WHEN a new procesamiento is uploaded
- THEN records are already created in these tables
- AND the Historial feature SHALL read from and delete from these existing tables only

## No Changes Required
No ADDED, MODIFIED, or REMOVED columns or tables. The feature is read-delete only against the current schema.
