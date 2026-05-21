import logging

logger = logging.getLogger(__name__)


class EmailGenerator:

    @staticmethod
    def generate_email_content(
        transacciones_unmatched: list[dict],
        tipo_resumen: str,
        periodo: str,
        destinatario: str,
        llm_router=None,
    ) -> tuple[str, str]:
        rows_html = "".join(
            f"<tr><td>{t.get('fecha', '')}</td><td>{t.get('descripcion', '')}</td>"
            f"<td style='text-align:right'>${t.get('monto', 0):.2f}</td></tr>"
            for t in transacciones_unmatched
        )

        asunto = f"Pagos sin comprobante fiscal — {tipo_resumen} — {periodo}"

        cuerpo_html = f"""
        <p>Estimado/a,</p>

        <p>Le informamos que, tras la revisión del resumen de tarjeta correspondiente al período <strong>{periodo}</strong>, se han identificado los siguientes pagos para los cuales <strong>no se encuentra comprobante fiscal asociado</strong> en nuestros registros:</p>

        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:100%; max-width:600px; font-family:Arial,sans-serif;">
            <thead>
                <tr style="background-color:#2563EB; color:white;">
                    <th>Fecha</th>
                    <th>Descripción</th>
                    <th>Monto</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        <p>Solicitamos la presentación de la documentación correspondiente a la brevedad.</p>

        <p>Sin otro particular, saludamos atentamente.</p>
        """

        if llm_router:
            try:
                lista_texto = "\n".join(
                    f"- {t.get('fecha', '')}: {t.get('descripcion', '')} — ${t.get('monto', 0):.2f}"
                    for t in transacciones_unmatched
                )
                prompt = (
                    f"Redactá un email PROFESIONAL y ESTRICTO en español.\n"
                    f"Asunto: Pagos sin comprobante fiscal — {tipo_resumen} — {periodo}\n\n"
                    f"El cuerpo debe incluir:\n"
                    f"- Saludo formal\n"
                    f"- Párrafo indicando que se detectaron pagos sin factura\n"
                    f"- Tabla con: Fecha, Descripción, Monto\n"
                    f"- Solicitud de presentación de comprobantes\n"
                    f"- Despedida formal\n\n"
                    f"Tono: estricto, profesional, sin confianzas.\n\n"
                    f"Transacciones sin factura:\n{lista_texto}\n\n"
                    f"Respondé SOLO con el asunto en la primera línea y el cuerpo HTML a continuación."
                )
                messages = [{"role": "user", "content": prompt}]
                respuesta = llm_router.chat(messages, task_type="email", max_tokens=1500)
                lineas = respuesta.strip().split("\n", 1)
                asunto_llm = lineas[0].strip()
                cuerpo_llm = lineas[1].strip() if len(lineas) > 1 else ""
                if asunto_llm and cuerpo_llm:
                    asunto = asunto_llm
                    cuerpo_html = cuerpo_llm
                logger.info("Email generado vía LLM para %s", tipo_resumen)
            except Exception as e:
                logger.warning("Error al generar email con LLM, usando fallback: %s", e)

        return asunto, cuerpo_html
