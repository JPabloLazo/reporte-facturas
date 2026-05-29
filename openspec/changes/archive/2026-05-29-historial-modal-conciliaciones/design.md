# Design: Historial Modal — Conciliaciones

## Technical Approach

Enhance the historial detail modal to show conciliación status per transacción (MATCHED/UNMATCHED/Sin procesar), with factura detail toggling. Backend: modify `GET /{resumen_id}` to LEFT OUTER JOIN through Conciliacion → Factura → FacturaDatos. Frontend: extend `renderTransactionRows` with optional conciliación columns + toggleable detail rows.

## Architecture Decisions

### Decision: Single-query JOIN vs N+1

**Choice**: Single `select().outerjoin()` chain in the existing endpoint
**Alternatives considered**: Multiple queries (one for transacciones, one for conciliaciones), subquery approach
**Rationale**: Existing `/historial` endpoint already uses a similar outerjoin pattern (lines 251–268). A single query with LEFT OUTER JOIN is idiomatic SQLAlchemy and avoids N+1. The result set is bounded per resumen (typically < 200 rows).

### Decision: Extend existing endpoint vs new endpoint

**Choice**: Modify `GET /{resumen_id}` (line 339) to always include conciliación data
**Alternatives considered**: New `/api/reports/{id}/detail` endpoint
**Rationale**: Only caller is `showHistorialDetailModal`. No existing consumer expects the old shape without conciliación fields — adding nullable fields is backward-compatible. Simpler deployment, no URL change.

### Decision: `renderTransactionRows` optional parameter vs separate function

**Choice**: Add 3rd parameter `includeConciliacion` (default falsy)
**Alternatives considered**: New `renderTransactionRowsWithConciliacion`, template inheritance
**Rationale**: Minimal duplication. `showTransactionsTable` stays unchanged. `showHistorialDetailModal` passes `true`. The conciliación columns are appended rather than interleaved, making the condition clean.

## Data Flow

```
User clicks "Ver detalle" in historial
  → showHistorialDetailModal(resumenId)
    → fetch GET /api/reports/{resumenId}
      → get_resumen() in reports.py
        → SELECT Transaccion, Conciliacion, Factura, FacturaDatos
             FROM transacciones
             LEFT OUTER JOIN conciliaciones ON transaccion_id
             LEFT OUTER JOIN facturas ON factura_id
             LEFT OUTER JOIN facturas_datos ON factura_id
             WHERE resumen_id = ?
    ← { transacciones: [{..., estado, confianza, metodo, factura: {...}}] }
  → renderTransactionRows('historial-modal-tbody', data, true)
  → 4 extra columns rendered after existing 5
  → Click "Ver factura" → toggle next-sibling hidden detail row
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/routers/reports.py` | Modify | Enhance `get_resumen` query + response shape |
| `app/static/js/main.js` | Modify | Extend `renderTransactionRows` signature + rendering; update `showHistorialDetailModal` caller |
| `app/templates/index.html` | Modify | Add 4 header columns to historial modal table |

## Interfaces / Contracts

### `GET /api/reports/{resumen_id}` — extended response

```python
# New field per transaction:
{
    "estado": "MATCHED" | "UNMATCHED" | None,
    "confianza": float | None,
    "metodo": str | None,
    "factura": {
        "id": int,
        "drive_file_name": str,
        "monto_total": float,
        "subtotal": float | None,
        "tipo_factura": str | None,
        "fecha": str,
        "vencimiento": str | None,
        "emisor": str | None,
        "cuit_emisor": str | None,
        "moneda": str | None,
        "numero_factura": str | None,
        "cuota_numero": int | None,
    } | None,
}
```

### Backend query — SQLAlchemy

```python
stmt = (
    select(Transaccion, Conciliacion, Factura, FacturaDatos)
    .outerjoin(Conciliacion, Conciliacion.transaccion_id == Transaccion.id)
    .outerjoin(Factura, Conciliacion.factura_id == Factura.id)
    .outerjoin(FacturaDatos, FacturaDatos.factura_id == Factura.id)
    .where(Transaccion.resumen_id == resumen_id)
    .order_by(Transaccion.fecha)
)
```

### Frontend — renderTransactionRows signature

```js
renderTransactionRows(tbodyId, data, includeConciliacion = false)
```

### Badge color logic

```
t.estado === "MATCHED"   → bg-green-100 text-green-700  "Match"
t.estado === "UNMATCHED" → bg-red-100 text-red-700      "Sin factura"
t.estado === null         → bg-gray-100 text-gray-600    "Sin procesar"
```

## Component Interaction

```
showHistorialDetailModal(id)
  → fetch /api/reports/{id}
  → renderTransactionRows('historial-modal-tbody', data, true)

showTransactionsTable(data)
  → renderTransactionRows('transactions-tbody', data)
```

### Modal table headers (index.html)

```html
<th class="text-center py-3 px-4 font-medium text-gray-600">Estado</th>
<th class="text-center py-3 px-4 font-medium text-gray-600">Confianza</th>
<th class="text-center py-3 px-4 font-medium text-gray-600">Método</th>
<th class="text-center py-3 px-4 font-medium text-gray-600">Factura</th>
```

## Error Handling

| Condition | Response behavior | UI behavior |
|-----------|-------------------|-------------|
| No Conciliacion row | `estado: null`, `confianza: null`, `metodo: null`, `factura: null` | Grey badge "Sin procesar" |
| Conciliacion exists but estado=UNMATCHED | `estado: "UNMATCHED"`, factura fields present, `factura: null` | Red badge "Sin factura" |
| Conciliacion exists, estado=MATCHED, but factura fields are null | `estado: "MATCHED"`, `factura: { ... with nulls }` | Green badge, missing factura fields show "—" inline |
| Resumen not found | 404 (unchanged) | Error message in modal |

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Response serialization with all estado combinations | Test endpoint with 3 mock scenarios |
| Integration | Query returns correct JOIN results | Seed transaccion + conciliacion + factura + datos, assert response |
| E2E | Historial modal renders badges + detail toggle | Manual verification via browser |

## Migration / Rollout

No migration required. The endpoint returns additional nullable fields; old calls are unchanged.
