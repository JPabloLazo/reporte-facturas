# Proposal: redesign-historial-modal

**Intent**: Replace the current "Ver detalle" flow (which navigates to the Procesar tab and mutates window._resumenId) with a modal overlay that keeps the user in the Historial context.

**Scope**: Frontend-only. index.html (modal markup) + main.js (new function, row click handler, removed loadResumenDetail side effects).

**Approach**: Follow the email-modal pattern (fixed inset-0, z-50, bg-opacity-50 overlay, centered panel). Lazy-fetch GET /api/reports/{id} on row click. Reuse shared renderTransactionRows helper. No tab switch, no window._resumenId mutation.

**Risk**: Low — all changes are additive or replace existing frontend behavior without touching backend.
