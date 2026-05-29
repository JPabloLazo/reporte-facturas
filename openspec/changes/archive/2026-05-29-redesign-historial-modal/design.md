# Design: Redesign Historial "Ver detalle" to Modal

## Technical Approach

Frontend-only change. Replace the current `loadResumenDetail` behavior (which navigates to the Procesar tab and populates `#transactions-section`) with a modal overlay that fetches and renders the detail inline. The modal follows the exact pattern established by `email-modal` in `base.html:49-66`.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| Render target | Inline modal overlay | Navigate to Procesar tab | User stays in Historial context; no tab switch, no state pollution |
| Modal pattern | email-modal (fixed inset-0, z-50, bg-opacity-50 overlay, centered panel) | card-modal pattern (flex centered) | email-modal has scrollable body + footer; card-modal is just a centered box — we need footer for action buttons |
| Data source | Lazy fetch GET /api/reports/{id} | Pre-fetch in initHistorial | Only fetch on demand (row click); no performance waste |
| Transaction rendering | Reuse `showTransactionsTable` logic but render into modal tbody | Duplicate rendering code | Avoids code duplication; inject modal tbody selector as parameter |
| resumen_id state | Read from `data.resumen_id` response field | Set `window._resumenId` | Zero side-effects on Procesar tab state; clean separation |
| Delete action | Close modal → DELETE API → refresh historial | Delete inline | Visual feedback: modal dismisses, item disappears from table |

## Data Flow

```
User clicks historial row
       │
       ▼
showHistorialDetailModal(resumenId)
       │
       ▼
GET /api/reports/{resumenId}
       │
       ├── Success ──→ render transactions into modal tbody
       │                  show modal (remove hidden)
       │
       ├── Error ────→ show red error state inside modal body
       │
       └── Delete ───→ DELETE /api/reports/historial/{id}
                          close modal
                          initHistorial() refresh
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/templates/index.html` | Modify | Add `#historial-modal` markup. Remove Acciones `<th>` and `<td>` from historial table. Add `cursor-pointer` to `<tr>`. |
| `app/static/js/main.js` | Modify | Remove `loadResumenDetail` function. Add `showHistorialDetailModal`, `closeHistorialModal`, `renderTransactionRows` shared helper. Wire row click to modal. |

## Error Handling

- Network/API failure → show error state inside modal body
- Empty transactions list → show empty-state message
- Delete failure → showToast(err.message, 'error')
