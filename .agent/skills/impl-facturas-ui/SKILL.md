---
name: impl-facturas-ui
description: >
  Crea la capa de UI: templates Jinja2 en app/templates/, estilos Tailwind CSS
  en app/static/css/, y JS en app/static/js/. Incluye página principal con 3
  tabs, drag & drop, tabla de resultados, formulario de configuración con
  recomendaciones de modelos LLM, y modal para asignar tarjeta a usuario.
  Trigger: Cuando se necesita crear o modificar la interfaz de usuario del frontend.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Se necesita crear la interfaz web del proyecto
- Se modifican templates, estilos, o JS
- Se agregan nuevas vistas o componentes UI

## Critical Patterns

- **Stack**: Jinja2 (integrado en FastAPI via `Jinja2Templates`), Tailwind CSS vía CDN, Vanilla JS (sin frameworks)
- **Estructura**: `app/templates/` para Jinja2, `app/static/css/` para CSS, `app/static/js/` para JS
- **Templates**: Usar `{% extends "base.html" %}` con blocks `{% block content %}` y `{% block scripts %}`
- **Tailwind**: Cargar desde CDN en `base.html`: `<script src="https://cdn.tailwindcss.com"></script>`
- **3 tabs**: Procesar, Configuración, Historial. Cada tab es un `div` con `class="hidden"`, se muestran con JS puro
- **Drag & drop**: Input file oculto + zona de drop con eventos `dragover`, `drop`, `dragleave`. Mostrar nombre de archivo soltado
- **Tabla de resultados**: Tabla HTML con `<thead>` fijo, scroll en `<tbody>`. Mostrar columnas: Archivo, Tipo, Monto, Fecha, Estado, Acciones
- **Configuración**: Formulario con campos: proveedor LLM (select), modelo (select), API key (password), SMTP host/port/user/pass. Mostrar recomendaciones de modelos según proveedor seleccionado
- **Modal asignar tarjeta**: Modal overlay con `<select>` de usuarios y tarjetas, botón Guardar/Cancelar
- **JS**: Un solo archivo `app/static/js/main.js` con funciones modulares (no jQuery)

## Code Examples

```html
<!-- app/templates/base.html -->
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Facturas{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body class="bg-gray-50">
    <nav class="bg-white shadow-sm">...</nav>
    <main class="container mx-auto p-4">
        {% block content %}{% endblock %}
    </main>
    <script src="/static/js/main.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

```javascript
// app/static/js/main.js
function showTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.add('hidden'));
    document.getElementById(tabId).classList.remove('hidden');
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
}

function setupDragDrop(zoneId) {
    const zone = document.getElementById(zoneId);
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('border-blue-500'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('border-blue-500'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('border-blue-500');
        const files = e.dataTransfer.files;
        // handle files
    });
}
```

## Commands

```bash
# Los templates se sirven automáticamente con FastAPI
# Los estáticos se sirven montando StaticFiles en main.py:
# app.mount("/static", StaticFiles(directory="app/static"), name="static")
```

## Dependencies

- **impl-facturas-infra** (debe ejecutarse antes — las rutas FastAPI y modelos deben existir)

## Resources

- `app/templates/` — directorio de templates Jinja2
  - `app/templates/base.html`
  - `app/templates/index.html`
  - `app/templates/config.html`
  - `app/templates/history.html`
  - `app/templates/modal_assign_card.html`
- `app/static/css/styles.css`
- `app/static/js/main.js`
