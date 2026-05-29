# Proposal: historial-modal-conciliaciones

**What**: Enriquecer modal de detalle del Historial con estado de conciliación, datos de factura, nombre de factura clickeable con detalle inline.

**Why**: User request. Need to show which transactions matched/unmatched with facturas in the historial detail modal.

**Where**:
- app/routers/reports.py (extend GET /api/reports/{id})
- app/templates/index.html (add 4 columns to modal table)
- app/static/js/main.js (extend renderTransactionRows, add inline expand)

**Scope**:
- Backend: extend GET /api/reports/{id} with LEFT JOINs to Conciliacion, Factura, FacturaDatos
- Frontend HTML: 4 new fixed columns: Estado, Factura, Monto factura, Confianza
- Frontend JS: renderTransactionRows with includeConciliacion flag, inline expand for factura details
- Transaccion sin conciliacion: badge gris "Sin procesar"
- Invoice name clickable → inline detail below row (Emisor, CUIT, Tipo, N° Factura, Fecha)
- Factura monto always visible, "—" when no invoice

**Decisions**:
- Inline expand over sub-modal or tooltip
- Single query with LEFT JOINs over N+1
- Extend shared renderTransactionRows helper with flag
- Grey "Sin procesar" badge for unconciliated transactions
