from fpdf import FPDF
import io


class PDFGenerator:

    @staticmethod
    def generate_transactions_pdf(resumen_info: dict, transacciones: list[dict]) -> bytes:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=20)

        # Header
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, "Resumen de Transacciones", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Resumen info
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, f"Tarjeta: {resumen_info.get('tipo', '-')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, f"Periodo: {resumen_info.get('periodo', '-')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, f"Archivo: {resumen_info.get('archivo', '-')}", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 7, f"Transacciones: {len(transacciones)}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(6)

        # Column widths
        col_fecha = 28
        col_desc = 72
        col_monto = 28
        col_cuotas = 24
        col_tipo = 28
        total_w = col_fecha + col_desc + col_monto + col_cuotas + col_tipo

        # Table header
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(41, 128, 185)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(col_fecha, 8, "Fecha", border=1, fill=True, align="C")
        pdf.cell(col_desc, 8, "Descripcion", border=1, fill=True, align="C")
        pdf.cell(col_monto, 8, "Monto", border=1, fill=True, align="C")
        pdf.cell(col_cuotas, 8, "Cuotas", border=1, fill=True, align="C")
        pdf.cell(col_tipo, 8, "Moneda", border=1, fill=True, align="C")
        pdf.ln()

        # Table rows
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(0, 0, 0)
        fill = False
        for t in transacciones:
            cuota_str = ""
            if t.get("cantidad_cuotas") and t["cantidad_cuotas"] > 1:
                cuota_str = f"{t.get('cuota_numero','?')}/{t['cantidad_cuotas']}"
            else:
                cuota_str = "-"

            if fill:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)

            monto_str = f"${t['monto']:,.2f}"

            pdf.cell(col_fecha, 7, str(t.get("fecha", "")), border=1, fill=True, align="C")
            pdf.cell(col_desc, 7, str(t.get("descripcion", ""))[:35], border=1, fill=True)
            pdf.cell(col_monto, 7, monto_str, border=1, fill=True, align="R")
            pdf.cell(col_cuotas, 7, cuota_str, border=1, fill=True, align="C")
            pdf.cell(col_tipo, 7, str(t.get("moneda", "ARS")), border=1, fill=True, align="C")
            pdf.ln()
            fill = not fill

        # Footer
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 5, "Generado por Reporte Facturas", align="C")

        return bytes(pdf.output())
