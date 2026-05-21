---
name: impl-facturas-pdf
description: >
  Implementa el parser de PDFs de resúmenes bancarios: AMEX (consolidado) y
  VISA (multitarjeta). Usa pdfplumber como parser primario. Fallback a LLM con
  visión cuando pdfplumber falla (facturas que son fotos de WhatsApp). Detección
  automática AMEX vs VISA. Crea app/services/pdf_parser.py y app/routes/upload.py.
  Trigger: Cuando se necesita parsear resúmenes de facturas desde PDFs subidos.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Se necesita parsear resúmenes AMEX o VISA desde archivos PDF
- Se agrega soporte para un nuevo tipo de resumen bancario
- Se modifica el pipeline de extracción de datos de PDFs

## Critical Patterns

- **Stack**: `pdfplumber` (parser principal), `Pillow` (manejo de imágenes para fallback)
- **Detección automática**: Inspeccionar primeras 3 páginas con pdfplumber. Buscar keywords: "AMEX", "American Express", "VISA", "Visa", "Banco". Según match, usar parser AMEX o VISA
- **Parser AMEX**: Resumen consolidado. Extraer: fecha de cierre, fecha de pago, monto total en pesos, monto total en USD, transacciones individuales (fecha, descripción, monto, moneda). El resumen AMEX tiene una sola tarjeta
- **Parser VISA**: Multitarjeta. El resumen puede contener múltiples tarjetas VISA (titular + adicionales). Extraer por cada tarjeta: los 4 últimos dígitos, responsable, transacciones. Identificar secciones por número de tarjeta
- **Fallback LLM visión**: Si pdfplumber extrae menos de 10 caracteres (PDF es imagen escaneada), convertir página a imagen con `pdf2image` y llamar a `llm_router.extract_with_vision()` con la imagen
- **Manejo de errores**: Si pdfplumber falla parcialmente, retornar lo que se pudo extraer + flag `partial: true`. Si falla totalmente, lanzar `PDFParseError` con mensaje descriptivo
- **Formato de salida**: Diccionario con keys: `tipo` (amex/visa), `tarjetas` (lista con transacciones), `resumen` (fecha_cierre, fecha_pago, total_ars, total_usd), `metadata` (archivo, páginas, modo_extracción)

## Code Examples

```python
# app/services/pdf_parser.py
import pdfplumber
from typing import Optional

def detectar_tipo(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:3]:
            text = page.extract_text() or ""
            if "american express" in text.lower():
                return "amex"
            if "visa" in text.lower() and "banco" in text.lower():
                return "visa"
    raise ValueError("Tipo de resumen no reconocido")

def parsear_amex(pdf_path: str) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    # Extraer fecha cierre, fecha pago, total ARS, total USD
    # Extraer tabla de transacciones (fecha, descripción, monto, moneda)
    return {"tipo": "amex", "tarjetas": [...], "resumen": {...}}

def parsear_visa(pdf_path: str) -> dict:
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    # Dividir por secciones de tarjeta (últimos 4 dígitos)
    # Extraer transacciones por tarjeta
    return {"tipo": "visa", "tarjetas": [...], "resumen": {...}}
```

## Commands

```bash
pip install pdfplumber Pillow pdf2image
```

## Dependencies

- **impl-facturas-infra** (debe ejecutarse antes — estructura de `app/`)
- **impl-facturas-extraccion** (debe ejecutarse antes — `llm_router` para fallback con visión)
- **impl-facturas-ui** (las rutas de upload necesitan templates existentes para renderizar respuesta)

## Resources

- `app/services/pdf_parser.py`
- `app/routes/upload.py`
- `app/routes/__init__.py`
- `app/services/__init__.py`
