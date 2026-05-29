# Proposal: fix-historial-tab

## Intent
Replace the static stub in the Historial tab with a functional, lazily-loaded list of past procesamientos. The database already stores Resumen, Transaccion, and Conciliacion records on every upload, but the UI has no way to list, view, download, or delete them.

## Scope

### In Scope
- Backend: new GET /api/reports/historial endpoint with aggregated counts (matched/unmatched/transactions) and pagination
- Frontend: lazy-load table on tab activation with period, type, file name, date, counts
- Row actions: view detail (reloads resumen into Procesar tab), download Excel/PDF, delete with confirmation
- Spinner: "Cargando historial..." while fetching

### Out of Scope
- In-app editing of historical records
- Server-side search/filter on historial columns
- Batch operations on multiple rows

## Approach
Add an async FastAPI router endpoint that returns a paginated list of Resumen rows with pre-computed counts via aggregated SQL to avoid N+1. On the frontend, add an `initHistorial()` function triggered when the Historial tab becomes active. Render rows using the existing vanilla-JS table pattern (document.createElement with Tailwind classes), and wire click handlers for view/download/delete. Follow the same fetch/showToast/modal patterns already used in main.js.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/routers/reports.py` | New | Add `/api/reports/historial` with counts and pagination |
| `app/templates/index.html` | Modified | Replace static stub with table and spinner markup |
| `app/static/js/main.js` | Modified | Add `initHistorial()`, row rendering, action handlers |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| N+1 query on large historial lists | Med | Use single aggregated SQL query with func.count |
| Stale data after new upload | Low | Call `initHistorial()` on each tab activation |
| Download links use wrong resumen_id | Low | Explicitly pass resumen.id per row, not global _resumenId |

## Rollback Plan
Remove the new endpoint, revert HTML stub, and remove initHistorial() and related handlers from main.js. No DB schema changes required.

## Dependencies
- None (uses existing DB tables and UI patterns)

## Success Criteria
- [ ] Historial tab shows real rows after upload with correct counts
- [ ] Clicking a row reloads its detail in the Procesar tab
- [ ] Excel and PDF download links work per row
- [ ] Delete removes the resumen and refreshes the list
- [ ] Spinner appears while loading and disappears after data arrives
