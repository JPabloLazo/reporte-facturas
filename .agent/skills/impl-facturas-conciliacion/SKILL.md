---
name: impl-facturas-conciliacion
description: >
  Implementa el motor de conciliación híbrido (SQL para match exacto por
  monto+fecha, LLM barato para edge cases), generación de Excel con openpyxl
  (solo transacciones UNMATCHED), y endpoints de procesamiento y descarga.
  Crea app/services/conciliador.py, app/services/excel_generator.py,
  app/routes/process.py, y app/routes/reports.py.
  Trigger: Cuando se necesita conciliar transacciones de facturas o generar reportes.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Se necesita ejecutar la conciliación entre facturas y resúmenes bancarios
- Se necesita generar reporte Excel con transacciones no conciliadas
- Se modifican las reglas de matching o el formato del Excel

## Critical Patterns

- **Stack**: `openpyxl` (generación Excel), SQLAlchemy (queries de matching)
- **Motor híbrido**: Dos fases:
  - **Fase 1 — Match exacto**: Query SQL que agrupa transacciones de factura vs resumen por `ABS(monto)` y `fecha` (mismo día). Match directo si monto y fecha coinciden → estado `MATCHED`
  - **Fase 2 — Edge cases LLM**: Transacciones sin match en Fase 1 se pasan a LLM barato (ej: `claude-3-haiku` o `gpt-4o-mini`) con contexto de ambos lados. El LLM decide si son match o no → estado `LLM_MATCHED` o `UNMATCHED`
- **conciliador.py**: Clase `Conciliador` con método `conciliar(facturas, resumenes) -> list[dict]`. Cada dict tiene: `id_factura`, `id_resumen`, `monto`, `fecha`, `estado` (MATCHED/LLM_MATCHED/UNMATCHED), `metodo` (sql/llm)
- **excel_generator.py**: Función `generar_excel(transacciones_unmatched: list) -> io.BytesIO`
  - Solo incluir transacciones con estado `UNMATCHED`
  - Columnas: Tipo (Factura/Resumen), Monto, Fecha, Descripción, Fuente (AMEX/VISA), Tarjeta
  - Formato: Encabezados en negrita, celdas con bordes, ancho de columna automático
  - Retornar `BytesIO` listo para descargar
- **process.py**: Endpoints: `POST /process/run` (ejecutar conciliación), `GET /process/status/{id}` (estado de procesamiento)
- **reports.py**: Endpoints: `GET /reports/download` (descargar Excel de no conciliados), `GET /reports/summary` (resumen de conciliación)
- **async**: El procesamiento debe ser async para no bloquear. Usar `BackgroundTasks` de FastAPI para ejecución larga

## Code Examples

```python
# app/services/conciliador.py
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Factura, TransaccionResumen

class Conciliador:
    def __init__(self, db: AsyncSession, llm_router=None):
        self.db = db
        self.llm_router = llm_router

    async def fase1_match_exacto(self, facturas, resumenes):
        matched = []
        # Agrupar por ABS(monto) + misma fecha
        for factura in facturas:
            for resumen in resumenes:
                if abs(factura.monto) == abs(resumen.monto) and factura.fecha == resumen.fecha:
                    matched.append({"factura": factura, "resumen": resumen, "metodo": "sql"})
                    resumenes.remove(resumen)
                    break
        return matched, resumenes

    async def fase2_match_llm(self, unmatched_facturas, unmatched_resumenes):
        if not self.llm_router:
            return [{"factura": f, "resumen": None, "metodo": "llm", "estado": "UNMATCHED"} for f in unmatched_facturas]
        # Prompt a LLM con pares candidatos
        ...
```

```python
# app/services/excel_generator.py
from openpyxl import Workbook
from openpyxl.styles import Font, Border, Side
import io

def generar_excel(unmatched: list) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    ws.title = "No Conciliados"
    header_font = Font(bold=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    headers = ["Tipo", "Monto", "Fecha", "Descripción", "Fuente", "Tarjeta"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.border = thin_border
    for row, item in enumerate(unmatched, 2):
        for col, key in enumerate(["tipo", "monto", "fecha", "descripcion", "fuente", "tarjeta"], 1):
            cell = ws.cell(row=row, column=col, value=item.get(key))
            cell.border = thin_border
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
```

## Commands

```bash
pip install openpyxl
```

## Dependencies

- **impl-facturas-infra** (debe ejecutarse antes — models, database)
- **impl-facturas-extraccion** (debe ejecutarse antes — `llm_router` para Fase 2)
- **impl-facturas-pdf** (debe ejecutarse antes — datos parseados de resúmenes)

## Resources

- `app/services/conciliador.py`
- `app/services/excel_generator.py`
- `app/routes/process.py`
- `app/routes/reports.py`
- `app/routes/__init__.py`
- `app/services/__init__.py`
