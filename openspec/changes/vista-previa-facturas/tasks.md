# Tasks: Vista Previa Editable de Facturas

## Phase 1: Backend Core — Modelo y Extracción

- [x] 1.1 `app/models.py` — agregar `cuota_numero = Column(Integer, nullable=True)` a FacturaDatos
- [x] 1.2 `app/services/conciliador.py:138` — cambiar `getattr(fd, 'cuota_numero', None)` → `fd.cuota_numero`
- [x] 1.3 `app/services/markitdown_extractor.py` — agregar `convert_with_fallback()`: revisa extensión (jpg/png/... → vision directo), para PDF: MarkItDown + heurística <50 chars → pdf2image→LLM vision
- [x] 1.4 `app/services/preview_service.py` — crear: pipeline descarga Drive → extracción paralela con fallback → InvoiceExtractor
- [x] 1.5 `app/routers/process.py` — agregar `POST /preview` con timeout 120s, errores no bloqueantes por factura
- [x] 1.6 `app/routers/process.py` — agregar `POST /save` con validaciones (monto numérico, fecha YYYY-MM-DD, cuota_numero entero opcional)

## Phase 2: Excel

- [x] 2.1 `app/services/excel_generator.py` — agregar `generate_invoices_preview_excel()` con columnas: Archivo, Método, Emisor, CUIT, Fecha, Vencimiento, Monto, Subtotal, Moneda, Tipo, N° Factura, Cuota N°, Texto
- [x] 2.2 `app/routers/process.py` — agregar `GET /preview/excel` que genera y devuelve Excel

## Phase 3: Frontend

- [x] 3.1 `app/templates/index.html` — agregar botón "Vista previa" junto a "Procesar conciliación" + contenedor de tabla editable con ActionBar
- [x] 3.2 `app/static/css/styles.css` — estilos para tabla editable, inputs inline, estados loading/error/editing/saved
- [x] 3.3 `app/static/js/main.js` — agregar `fetchPreview()` (dispara POST /preview), `renderEditableTable()` (tabla con inputs), `handleSave()` (POST /save), máquina de estados idle→loading→preview→editing→saving→saved

## Phase 4: Testing

- [ ] 4.1 Unit: pipeline `convert_with_fallback()` detecta PDF imagen (<50 chars → vision fallback)
- [ ] 4.2 Unit: validaciones de `POST /save` (montos inválidos, fechas mal formateadas, cuota_numero no entero)
- [ ] 4.3 Integration: flujo Preview → Save → leer FacturaDatos de DB con cuota_numero persistido
- [ ] 4.4 Frontend: tabla editable carga datos de preview, botón Guardar deshabilitado si faltan campos requeridos
