import io

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


class ExcelGenerator:
    @staticmethod
    def generate_unmatched_excel(
        resumen_info: dict,
        transacciones: list,
        nombre_archivo: str = "pagos_sin_factura.xlsx",
    ) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Pagos sin Factura"

        ws.merge_cells("A1:F1")
        cell = ws.cell(
            row=1,
            column=1,
            value=f"Pagos sin Factura Asociada - {resumen_info.get('periodo', '')}",
        )
        cell.font = Font(bold=True, size=14)

        ws.merge_cells("A2:F2")
        ws.cell(
            row=2, column=1, value=f"Tipo: {resumen_info.get('tipo', '')}"
        )

        headers = ["Fecha", "Descripción", "Monto", "Tarjeta", "Moneda", "Período"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(
                start_color="2563EB", end_color="2563EB", fill_type="solid"
            )
            cell.alignment = Alignment(horizontal="center")

        for i, t in enumerate(transacciones, 5):
            ws.cell(row=i, column=1, value=t.get("fecha", ""))
            ws.cell(row=i, column=2, value=t.get("descripcion", ""))
            ws.cell(row=i, column=3, value=t.get("monto", 0))
            ws.cell(row=i, column=4, value=t.get("numero_tarjeta", ""))
            ws.cell(row=i, column=5, value=t.get("moneda", "ARS"))
            ws.cell(row=i, column=6, value=resumen_info.get("periodo", ""))

        ws.column_dimensions["A"].width = 14
        ws.column_dimensions["B"].width = 40
        ws.column_dimensions["C"].width = 12
        ws.column_dimensions["D"].width = 16
        ws.column_dimensions["E"].width = 10
        ws.column_dimensions["F"].width = 10

        output = io.BytesIO()
        wb.save(output)
        return output.getvalue()
