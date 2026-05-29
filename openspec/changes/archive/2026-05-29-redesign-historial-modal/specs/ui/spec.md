# Delta for ui/historial-table

## REMOVED Requirements

### Requirement: Acciones column and inline action buttons

(Reason: Replaced by clickable-row-to-modal pattern. Actions moved inside modal overlay.)

## MODIFIED Requirements

### Requirement: Historial table row interactivity

Previously: Rows were non-interactive static data. Action buttons (Ver detalle, Excel, PDF, Eliminar) rendered in the Acciones column.

The system MUST make each historial table row fully clickable.
The system MUST apply cursor-pointer style to rows.
The system MUST remove the Acciones `<th>` and `<td>` from all rows.

#### Scenario: Row click opens detail modal

- GIVEN a historial table with one or more items
- WHEN the user clicks anywhere on a row (not a child button/link)
- THEN the system calls showHistorialDetailModal with the item's resumen ID
- AND no tab switch or window._resumenId mutation occurs

# Delta for ui/historial-detail-modal

## ADDED Requirements

### Requirement: Historial detail modal component

The system MUST render a new modal overlay (z-50) triggered by row click.
The modal MUST include: a header row displaying Periodo, Tipo, and Archivo nombre; a read-only transaction table; a Download Excel button; a Download PDF button; a Delete button; and a close button (×).

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

# Delta for js/historial-interaction

## REMOVED Requirements

### Requirement: loadResumenDetail — tab switch + _resumenId mutation

(Reason: The old function mutated window._resumenId and switched to the Procesar tab. Both behaviors are removed. The new modal-based flow replaces this entirely.)

The following behaviors MUST be removed:
- `window._resumenId = data.id` assignment from the fetch callback
- `document.querySelector('[data-tab="procesar"]').click()` tab switch
- `file-info` DOM mutation (rendering file header in procesar tab)

#### Scenario: No side effects on historial row click

- GIVEN a historial item exists
- WHEN the user clicks the row
- THEN window._resumenId MUST NOT change
- AND the active tab MUST remain "Historial"
- AND no element with id "file-info" is modified

## MODIFIED Requirements

### Requirement: initHistorial — button-free row rendering

Previously: initHistorial rendered 4 action buttons per row (Ver detalle, Excel, PDF, Eliminar) and attached click handlers for each.

The system MUST render rows WITHOUT action buttons or Acciones td.
The system MUST attach a single click handler per row that calls showHistorialDetailModal(item.id).
Download and delete actions are available exclusively inside the modal.

#### Scenario: Historial table renders without actions column

- GIVEN initHistorial() fetches data from /api/reports/historial
- WHEN rows are rendered in #historial-tbody
- THEN no row contains a .historial-btn-detail, .historial-btn-excel, .historial-btn-pdf, or .historial-btn-delete element
- AND clicking a row fires showHistorialDetailModal

## ADDED Requirements

### Requirement: showHistorialDetailModal function

The system MUST add a new function `showHistorialDetailModal(resumenId)` that:
- Fetches GET /api/reports/{resumenId}
- On success: populates a modal with header fields and transaction table, shows the modal
- On error: shows a toast with the error message
- Inside the modal: wires Excel, PDF, delete, and close button handlers

#### Scenario: showHistorialDetailModal loads and displays

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
