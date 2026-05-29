# Design: fix-historial-tab

## Technical Approach

Add a paginated GET `/api/reports/historial` endpoint that returns `Resumen` rows with pre-computed transaction, matched, and unmatched counts using a single aggregated SQL query. On the frontend, wire the Historial tab to lazy-load this list on activation, render a vanilla-JS table with Tailwind classes, and attach per-row action handlers for view, download, and delete.

## Architecture Decisions

| Decision | Option A (chosen) | Option B (rejected) | Rationale |
|----------|-------------------|----------------------|-----------|
| Endpoint placement | Extend `app/routers/reports.py` | New router | Reports router already owns resumen-scoped downloads; adding one list endpoint keeps cohesion. |
| Count aggregation | Single query with `func.count` + `case` | Separate queries per resumen | Avoids N+1; one round-trip for the entire page. |
| Pagination | Offset/limit with fixed page size | Cursor-based | Dataset is small (hundreds of resumenes); offset is simpler and sufficient. |
| Delete cascade | DB `CASCADE` on FKs | Manual multi-step delete | Schema already has `CASCADE`; `DELETE FROM resumenes WHERE id = :id` cleans up children automatically. |
| Frontend trigger | `initHistorial()` on every tab click | Single fetch on app load | Guarantees fresh data after uploads without complex invalidation logic. |
| Row state storage | `data-resumen-id` on `<tr>` | Global `window._historialResumenId` | Keeps action handlers declarative and avoids stale global state when scrolling/re-rendering. |

## Data Flow

```
User clicks "Historial" tab
        │
        ▼
initHistorial() ──► show spinner
        │
        ▼
GET /api/reports/historial?offset=0&limit=20
        │
        ▼
Backend: aggregated SQL query (Resumen + counts)
        │
        ▼
Render rows into #historial-tbody
        │
        ▼
Attach per-row click handlers (view / download / delete)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/routers/reports.py` | Modify | Add `GET /historial` endpoint with counts, pagination, and `DELETE /historial/{resumen_id}`. |
| `app/templates/index.html` | Modify | Replace static Historial stub with table markup, spinner, and empty-state placeholder. |
| `app/static/js/main.js` | Modify | Add `initHistorial()`, row renderers, action handlers, and spinner toggle. |

## Interfaces / Contracts

### `GET /api/reports/historial`
Query params:
- `offset` (int, default 0, min 0)
- `limit` (int, default 20, min 1, max 100)

Response (200):
```json
{
  "items": [
    {
      "id": 1,
      "periodo": "2026-05",
      "tipo": "VISA",
      "archivo_nombre": "resumen.pdf",
      "fecha_procesado": "2026-05-29T13:44:53",
      "total_transacciones": 42,
      "matched": 35,
      "unmatched": 7
    }
  ],
  "total": 150
}
```

### `DELETE /api/reports/historial/{resumen_id}`
Response (200): `{"status": "deleted"}`  
Response (404): Standard FastAPI `HTTPException(404)`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Aggregated count query correctness | Inline SQLAlchemy test with known fixtures |
| Integration | `GET /historial` returns correct shape and pagination | `TestClient` against FastAPI app with seeded DB |
| Integration | `DELETE` cascades and returns 404 on missing ID | `TestClient` + DB assertion |
| E2E | Tab activation renders rows, delete shows confirmation | Manual browser verification |

## Migration / Rollout

No migration required. Uses existing tables (`resumenes`, `transacciones`, `conciliaciones`) with existing `CASCADE` foreign keys.

## Open Questions

- None. All dependencies are satisfied by existing schema and patterns.
