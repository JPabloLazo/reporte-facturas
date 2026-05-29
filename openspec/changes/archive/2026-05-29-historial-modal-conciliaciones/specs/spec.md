# Delta Specs: historial-modal-conciliaciones

## Domain: backend/reports

### MODIFIED Requirement: GET /api/reports/{id} Conciliaciones

The system MUST return conciliaciones data alongside transacciones in the GET /api/reports/{id} response.

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

---

## Domain: ui/historial-modal

### MODIFIED Requirement: Historial Modal Table Columns

The system MUST display 4 additional columns in the historial detail modal table: Estado, Factura, Monto factura, Confianza.

| Column | Content |
|--------|---------|
| Estado | Badge: green "Match" (MATCHED), red "Sin factura" (UNMATCHED), grey "Sin procesar" (no conciliacion) |
| Factura | Clickable factura name (drive_file_name), shows "—" if null |
| Monto factura | Formatted currency ($X.XX) from factura_datos.monto_total, shows "—" if null |
| Confianza | Percentage (e.g., "95%") from conciliacion.confianza, shows "—" if null |

The existing columns (Fecha, Descripción, Monto, Moneda, Cuota) MUST remain unchanged.

#### Scenario: Transaction with MATCHED conciliacion

- GIVEN a transaccion with conciliacion.estado = "MATCHED" and factura data present
- WHEN the historial modal renders the table row
- THEN Estado shows a green "Match" badge, Factura shows clickable drive_file_name, Monto factura shows formatted monto_total, Confianza shows confianza as percentage

#### Scenario: Transaction with UNMATCHED conciliacion

- GIVEN a transaccion with conciliacion.estado = "UNMATCHED" and factura = null
- WHEN the historial modal renders the table row
- THEN Estado shows a red "Sin factura" badge, Factura shows "—", Monto factura shows "—", Confianza shows confianza as percentage

#### Scenario: Transaction with NO conciliacion

- GIVEN a transaccion with conciliacion = null
- WHEN the historial modal renders the table row
- THEN Estado shows a grey "Sin procesar" badge, Factura shows "—", Monto factura shows "—", Confianza shows "—"

---

## Domain: js/historial-modal

### MODIFIED Requirement: Inline Factura Detail Expand

The Factura column value in each row MUST be a clickable button/toggle that reveals a hidden detail row below the current row showing factura metadata.

The detail row MUST display: Emisor, CUIT, Tipo (tipo_factura), N° Factura (numero_factura), Fecha (factura_datos.fecha).

A second click on the same factura name MUST collapse the detail row.

#### Scenario: Click to expand

- GIVEN a row with a visible factura name (MATCHED conciliacion)
- WHEN the user clicks the factura name
- THEN a detail row appears directly below with Emisor, CUIT, Tipo, N° Factura, and Fecha values from factura_datos

#### Scenario: Click to collapse

- GIVEN an expanded detail row visible below a transaction row
- WHEN the user clicks the same factura name again
- THEN the detail row is removed from the DOM

#### Scenario: Fast double-click safety

- GIVEN a factura name button that is currently expanding (DOM being modified)
- WHEN the user clicks rapidly twice
- THEN only one detail row is created (no duplicate rows); subsequent clicks toggle normally
