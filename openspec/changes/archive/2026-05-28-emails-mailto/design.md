# Design: Email Generation via mailto:

## Technical Approach

Reemplazar envío SMTP por endpoint de preview que retorna borradores agrupados por titular de tarjeta usando el LLM existente, modal editable en frontend, y apertura de `mailto:` al confirmar. Eliminar todo el código SMTP del stack.

## Architecture Decisions

### Decision: Preview endpoint stateless (POST, no escribe DB)

**Choice**: `POST /api/reports/{resumen_id}/email/preview` consulta UNMATCHED + TarjetaUsuario, llama al LLM, retorna JSON.
**Alternatives**: Mantener envío SMTP, enviar directo sin preview.
**Rationale**: Stateless = sin datos huérfanos, el usuario puede regenerar cuantas veces quiera. El LLM se llama igual, pero el usuario revisa antes de enviar.

### Decision: LLM genera body en dos formatos (HTML + texto plano)

| Opción | Tradeoff | Decisión |
|--------|----------|----------|
| body_html solo | No sirve para mailto (clientes no renderizan HTML) | ❌ |
| body_text solo | Preview en modal pierde formato | ❌ |
| **Ambos** | Una llamada LLM extra, prompt más largo | ✅ |

**Choice**: El prompt pide `body_html` (para preview en modal) y `body_text` (para mailto).
**Rationale**: El modal necesita HTML formateado (tablas, estilos). mailto solo acepta texto plano confiablemente. Una sola llamada LLM genera ambos.

### Decision: Agrupación por tarjeta → un email por titular

**Choice**: El LLM recibe la lista completa de transacciones UNMATCHED + todas las TarjetaUsuario, y el prompt le pide agrupar por titular. Retorna un array de emails, uno por titular con transacciones filtradas.
**Alternatives**: Backend agrupa y llama al LLM por separado para cada titular.
**Rationale**: El LLM puede razonar qué transacciones pertenecen a cada tarjeta (por `numero_tarjeta`) en una sola llamada, reduciendo latencia y tokens totales.

### Decision: mailto: vía window.open

**Choice**: `window.open('mailto:?to=...&subject=...&body=...')` al confirmar cada email.
**Alternatives**: fetch a endpoint de envío, clipboard + instrucción manual.
**Rationale**: Sin dependencia de servidor SMTP. El usuario confirma el envío en su cliente local. `window.open` evita navegación de la página actual.

### Decision: Eliminar SMTP del código (no deprecar)

**Choice**: Borrar `email_sender.py`, campos SMTP de Settings, config router, config template, y JS.
**Rationale**: Código muerto = deuda técnica. El nuevo flujo no usa SMTP. Si se necesita en futuro, git conserva el historial.

## Data Flow

```
Usuario → Click "Enviar emails" en tabla de resultados
    │
    ▼
fetch('POST /api/reports/{id}/email/preview')
    │
    ▼
reports.py: email_preview()
    ├─ db: select Resumen
    ├─ db: select Conciliacion UNMATCHED + Transaccion (join)
    ├─ db: select TarjetaUsuario (all)
    ├─ EmailGenerator.generate_emails(unmatched, tarjetas, resumen, llm_router)
    │     └─ LLM chat prompt → JSON [{to, name, subject, body_html, body_text}]
    │     └─ fallback template si LLM falla
    └─ return JSON { emails: [...] }
    │
    ▼
Modal preview en base.html:
    ├─ Lista de borradores (to, subject, body_html renderizado)
    ├─ Inputs editables por campo
    ├─ Botón "Eliminar" por email
    ├─ Botón "Cancelar" → cierra modal
    └─ Botón "Enviar" (por email):
          window.open('mailto:to&subject&body')
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/routers/reports.py` | Modify | Replace `POST /{id}/email` with `POST /{id}/email/preview`; remove SMTP check, return JSON drafts |
| `app/services/email_generator.py` | Modify | New `generate_emails()` method — receives unmatched + tarjetas, calls LLM once, returns list of drafts with `body_html` + `body_text` |
| `app/services/email_sender.py` | Delete | Entire file — no longer needed |
| `app/routers/config.py` | Modify | Remove `smtp_*` from GET response and PUT mapping |
| `app/templates/config.html` | Modify | Remove SMTP section (host/port/user/pass fields) |
| `app/templates/base.html` | Modify | Add email preview modal HTML |
| `app/static/js/main.js` | Modify | Remove SMTP from `initConfig()`/`loadConfig()`; add `initEmailModal()` + `fetchEmailPreview()` + `openMailto()` |
| `app/static/css/styles.css` | Modify | Add modal styles for email preview |
| `app/config.py` | Modify | Remove `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `email_from` from Settings; keep `email_responsable` |

## Interfaces

### New Endpoint

```python
POST /api/reports/{resumen_id}/email/preview
Response 200:
{
  "emails": [
    {
      "recipient_email": "user@corp.com",
      "recipient_name": "Juan Pérez",
      "subject": "Pagos sin comprobante — VISA — 01/2026",
      "body_html": "<p>Estimado/a Juan,</p><table>...</table>",
      "body_text": "Estimado/a Juan,\n\nTransacciones sin factura:\n- 15/01: Compra X — $1500.00\n\nSaludos."
    }
  ]
}
```

### EmailGenerator.generate_emails()

```python
@staticmethod
def generate_emails(
    transacciones_unmatched: list[dict],
    tarjetas: list[TarjetaUsuario],
    tipo_resumen: str,
    periodo: str,
    llm_router,
) -> list[dict]:
```

Returns list of dicts with keys: `recipient_email`, `recipient_name`, `subject`, `body_html`, `body_text`.

### LLM Prompt (single call, grouped by card holder)

```python
prompt = f"""
Resumen: {tipo} - {periodo}

Transacciones sin factura:
{lista_transacciones}

Tarjetas registradas:
{lista_tarjetas}

Agrupá las transacciones por titular de tarjeta y generá un email profesional para cada uno.
NO inventes destinatarios. Solo usá los emails de las tarjetas registradas.
Respondé SOLO con JSON válido en este formato:
[
  {{
    "recipient_email": "email@ejemplo.com",
    "recipient_name": "Nombre Apellido",
    "subject": "Asunto del email",
    "body_html": "<p>Cuerpo HTML del email</p>",
    "body_text": "Cuerpo en texto plano con saltos de línea"
  }}
]
"""
```

### Mailto generation (JS)

```javascript
var mailtoLink = 'mailto:' + encodeURIComponent(to) +
    '?subject=' + encodeURIComponent(subject) +
    '&body=' + encodeURIComponent(bodyText);
window.open(mailtoLink);
```

## Testing Strategy

No test framework detected in project. Manual verification checklist:

| Layer | What | How |
|-------|------|-----|
| Backend | Preview endpoint returns valid JSON | Manual: curl POST /api/reports/{id}/email/preview |
| Backend | LLM fallback on error | Inducir error de LLM, verificar template de respaldo |
| Backend | SMTP fields removed | Confirmar GET /api/config no devuelve smtp_* |
| Frontend | Modal muestra borradores editables | Click "Enviar emails", verificar to/subject/body editables |
| Frontend | Mailto abre correctamente | Click "Enviar", verificar cliente de email con datos prellenados |
| Frontend | Config sin SMTP | Abrir pestaña Config, sección SMTP no debe existir |

## Migration

No migration required. SMTP settings existentes en DB (`settings` table) quedan huérfanas pero no causan errores. Se pueden limpiar manualmente con `DELETE FROM settings WHERE key LIKE 'smtp_%'`.

## Open Questions

None.
