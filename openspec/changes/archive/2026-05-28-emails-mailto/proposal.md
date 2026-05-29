# Proposal: emails-mailto

## Intent

Reemplazar el envío de emails vía SMTP por links `mailto:` que abren el cliente de email del usuario. Eliminar dependencia de servidor SMTP y dar control al usuario para editar destinatario, asunto y cuerpo antes de enviar.

## Scope

### In Scope
- Endpoint `POST /api/reports/{id}/email/preview` — recopila unmatched + tarjetas, LLM genera borradores por titular
- Modal editable en frontend para previsualizar/editar to, subject, body por titular
- Apertura de `mailto:` con datos prellenados al confirmar
- `EmailGenerator.generate_multiple_emails()` — agrupa transacciones por titular, delega al LLM, retorna lista de emails
- Eliminar `app/services/email_sender.py` completo
- Eliminar campos SMTP de `app/config.py`, `app/routers/config.py`, `app/templates/config.html`, `app/static/js/main.js`
- El LLM solo usa emails registrados en `tarjetas_usuarios`; no inventa destinatarios
- Sin adjunto Excel (tabla inline en el HTML)

### Out of Scope
- Consolidación de múltiples titulares en un solo email
- Historial de emails enviados
- Retry automático si el LLM falla

## Approach

Tres capas: (1) backend — nuevo endpoint de preview que agrupa transacciones por tarjeta, llama al LLM por cada titular y retorna borradores; (2) frontend — modal con campos editables por cada email generado; (3) cleanup — eliminar SMTP de config router, settings, templates y JS. El botón "Enviar" del modal construye y abre `mailto:` en lugar de llamar a SMTP.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/routers/reports.py` | Modified | Reemplazar `POST /{id}/email` por preview + mailto |
| `app/services/email_generator.py` | Modified | Retornar lista de emails agrupados por titular |
| `app/services/email_sender.py` | Removed | Archivo completo |
| `app/config.py` | Modified | Eliminar `smtp_host/port/user/password/from/responsable` |
| `app/routers/config.py` | Modified | Eliminar SMTP de mapping y response |
| `app/templates/config.html` | Modified | Eliminar sección SMTP |
| `app/templates/base.html` | Modified | Agregar modal de preview de emails |
| `app/static/js/main.js` | Modified | Eliminar SMTP de initConfig/loadConfig; agregar preview y mailto |
| `app/static/css/styles.css` | Modified | Estilos para modal de preview |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| LLM genera destinatario no registrado | Low | Backend filtra: solo emails de `tarjetas_usuarios`; si no hay, no incluir ese grupo |
| LLM falla en generar cuerpo HTML | Med | Fallback a template estático inline |
| Usuario cierra modal sin enviar y pierde borradores | Med | No hay estado que perder — puede regenerar con preview |

## Rollback Plan

`git checkout -- app/routers/reports.py app/services/email_generator.py app/config.py app/routers/config.py app/templates/config.html app/templates/base.html app/static/js/main.js app/static/css/styles.css`. Restaurar `app/services/email_sender.py` del último commit.

## Dependencies

- API key de OpenRouter configurada (ya existente)

## Success Criteria

- [ ] `/api/reports/{id}/email/preview` retorna lista de borradores con emails reales de tarjetas registradas
- [ ] Modal muestra borradores editables (to, subject, body)
- [ ] Confirmar abre `mailto:` con datos prellenados
- [ ] No queda código SMTP en backend ni frontend
