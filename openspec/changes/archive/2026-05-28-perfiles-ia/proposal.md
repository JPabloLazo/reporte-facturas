# Proposal: perfiles-ia

## Intent

Reemplazar la configuración granular de modelos IA (4 selects + API keys en UI) por 3 perfiles predefinidos (Rápido, Optimizado, Lento) que definen stacks completos para extracción, visión, conciliación y emails. OpenRouter es el único proveedor.

## Scope

### In Scope
- Diccionario `IA_PROFILES` en `app/config.py` con 3 stacks de modelos
- Simplificar endpoints de configuración: solo leer/guardar `ia_profile`
- Eliminar selects de modelos y API keys de la UI
- Clase `LLMError` con tipificación de errores de OpenRouter
- Capturar `LLMError` en routers (upload, process, reports) con códigos HTTP apropiados
- Modal emergente en frontend para errores de OpenRouter
- Estilos CSS para tarjetas de perfil y modal

### Out of Scope
- Carga dinámica de modelos
- Fallbacks entre perfiles
- Otros proveedores que no sean OpenRouter
- Tests automatizados
- Migración de settings existentes

## Approach

Tres capas: (1) backend — reemplazar modelo/proveedor por `ia_profile`; (2) servicios LLM — `LLMError` con parseo de errores OpenRouter; (3) frontend — reemplazar 4 selects y API keys por 3 tarjetas de perfil + modal de errores.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/config.py` | Modified | Agregar `IA_PROFILES` dict |
| `app/routers/config.py` | Modified | Endpoints solo `ia_profile` |
| `app/services/llm_router.py` | Modified | Agregar `LLMError`, resolver desde perfil |
| `app/routers/{upload,process,reports}.py` | Modified | Capturar `LLMError` |
| `app/templates/{config,base}.html` | Modified | Tarjetas + markup modal |
| `app/static/js/main.js` | Modified | Eliminar `loadAvailableModels`, agregar modal |
| `app/static/css/styles.css` | Modified | Estilos modal y tarjetas |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Perfiles hardcodeados obsoletos si OpenRouter cambia modelos | Med | Centralizado en `config.py`; cambio único |
| Usuarios pierden API keys previas | High | Documentar en changelog |
| Error parseando respuesta OpenRouter | Low | `LLMError` tipo `unknown` como catch-all |

## Rollback Plan

`git checkout -- app/config.py app/routers/config.py app/services/llm_router.py app/routers/upload.py app/routers/process.py app/routers/reports.py app/templates/config.html app/templates/base.html app/static/js/main.js app/static/css/styles.css`. La UI vuelve a selects y API keys.

## Dependencies

- API key de OpenRouter en `.env` como `OPENROUTER_API_KEY`

## Success Criteria

- [ ] Usuario selecciona perfil y se guarda
- [ ] Las 4 tareas usan modelos del perfil seleccionado
- [ ] Modal de error aparece con mensaje específico
- [ ] API keys no aparecen en la UI
