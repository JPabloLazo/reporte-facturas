import json
import logging
import re
from collections import defaultdict

from app.services.llm_router import LLMError

logger = logging.getLogger(__name__)


class EmailGenerator:

    @staticmethod
    def generate_emails(
        transacciones_unmatched: list[dict],
        tipo_resumen: str,
        periodo: str,
        tarjetas: list[dict],
        llm_router=None,
    ) -> list[dict]:
        """
        Genera borradores de email agrupados por titular de tarjeta.

        Parámetros:
            transacciones_unmatched: list[dict] con keys id, fecha, descripcion, monto, numero_tarjeta, moneda
            tipo_resumen: str (VISA, AMEX, etc.)
            periodo: str (ej. "2026-05")
            tarjetas: list[dict] con keys numero_tarjeta, nombre_usuario, email_usuario
            llm_router: instancia de LLMRouter o None

        Retorna:
            list[dict] con keys: recipient_email, recipient_name, subject,
                                 body_html, body_text, card_numbers, transaction_ids
        """
        if llm_router:
            try:
                return EmailGenerator._generate_via_llm(
                    transacciones_unmatched, tipo_resumen, periodo,
                    tarjetas, llm_router,
                )
            except LLMError:
                raise
            except Exception as e:
                logger.warning(
                    "Error al generar emails con LLM, usando fallback: %s", e
                )

        return EmailGenerator._generate_fallback(
            transacciones_unmatched, tipo_resumen, periodo, tarjetas,
        )

    @staticmethod
    def _generate_via_llm(
        transacciones_unmatched: list[dict],
        tipo_resumen: str,
        periodo: str,
        tarjetas: list[dict],
        llm_router,
    ) -> list[dict]:
        transacciones_json = json.dumps(
            [
                {
                    "id": t.get("id"),
                    "fecha": t.get("fecha", ""),
                    "descripcion": t.get("descripcion", ""),
                    "monto": t.get("monto", 0),
                    "numero_tarjeta": t.get("numero_tarjeta", ""),
                    "moneda": t.get("moneda", "ARS"),
                }
                for t in transacciones_unmatched
            ],
            ensure_ascii=False,
            indent=2,
        )

        tarjetas_json = json.dumps(
            [
                {
                    "numero_tarjeta": t["numero_tarjeta"],
                    "nombre_usuario": t.get("nombre_usuario", ""),
                    "email_usuario": t.get("email_usuario", ""),
                }
                for t in tarjetas
            ],
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""Resumen: {tipo_resumen} — {periodo}

Transacciones sin factura (id, fecha, descripcion, monto, numero_tarjeta, moneda):
{transacciones_json}

Tarjetas registradas:
{tarjetas_json}

Agrupá las transacciones por titular de tarjeta y generá un email profesional en español para cada uno.
NO inventes destinatarios. Solo usá los emails de las tarjetas registradas.
Si un número de tarjeta no tiene titular registrado, asignalo al primer responsable de la lista.
Respondé SOLO con JSON válido. Sin markdown, sin comentarios.

Formato:
[
  {{
    "recipient_email": "email@ejemplo.com",
    "recipient_name": "Nombre Apellido",
    "subject": "Pagos sin comprobante — {tipo_resumen} — {periodo}",
    "body_html": "<p>Estimado/a Nombre,</p><p>...</p><table>...</table><p>Saludos.</p>",
    "body_text": "Estimado/a Nombre,\\n\\nSe han detectado...\\n\\n1. 15/05/2026 - Descripción - $500.00\\n\\nSaludos.",
    "card_numbers": ["****42000"],
    "transaction_ids": [1, 2, 3]
  }}
]

- body_html: HTML completo con tabla de transacciones, profesional en español.
- body_text: Texto plano con lista numerada de transacciones (para mailto).
- card_numbers: números de tarjeta asociados a este email.
- transaction_ids: IDs de las transacciones incluidas en este email.
- Tono: profesional, formal, estricto."""

        messages = [{"role": "user", "content": prompt}]
        respuesta = llm_router.chat(messages, task_type="email", max_tokens=3000)

        emails = EmailGenerator._parse_llm_json(respuesta)

        if not isinstance(emails, list):
            raise ValueError("LLM response is not a JSON array")

        for email in emails:
            email.setdefault("card_numbers", [])
            email.setdefault("transaction_ids", [])
            email.setdefault("body_text", "")

        logger.info(
            "Emails generados vía LLM para %s: %d destinatarios",
            tipo_resumen,
            len(emails),
        )
        return emails

    @staticmethod
    def _parse_llm_json(resp: str) -> list:
        resp = resp.strip()
        resp = re.sub(r"^```(?:json)?\s*\n?", "", resp)
        resp = re.sub(r"\n?```\s*$", "", resp)
        resp = resp.strip()
        return json.loads(resp)

    @staticmethod
    def _generate_fallback(
        transacciones_unmatched: list[dict],
        tipo_resumen: str,
        periodo: str,
        tarjetas: list[dict],
    ) -> list[dict]:
        card_to_holder = {t["numero_tarjeta"]: t for t in tarjetas}

        by_card = defaultdict(list)
        for t in transacciones_unmatched:
            by_card[t.get("numero_tarjeta", "") or ""].append(t)

        groups: dict[str, dict] = {}
        for num, trans in by_card.items():
            holder = card_to_holder.get(num)
            if holder and holder.get("email_usuario"):
                email = holder["email_usuario"]
                if email not in groups:
                    groups[email] = {
                        "transactions": [],
                        "card_numbers": set(),
                        "name": holder.get("nombre_usuario", "responsable"),
                        "email": email,
                    }
                groups[email]["transactions"].extend(trans)
                if num:
                    groups[email]["card_numbers"].add(num)
            else:
                first = next(
                    (t for t in tarjetas if t.get("email_usuario")), None
                )
                email = first["email_usuario"] if first else ""
                name = (
                    first.get("nombre_usuario", "responsable")
                    if first
                    else "responsable"
                )
                key = email or f"__unassigned__{num}"
                if key not in groups:
                    groups[key] = {
                        "transactions": [],
                        "card_numbers": set(),
                        "name": name,
                        "email": email,
                    }
                groups[key]["transactions"].extend(trans)
                if num:
                    groups[key]["card_numbers"].add(num)

        emails = []
        for group in groups.values():
            trans = group["transactions"]
            transaction_ids = [t.get("id") for t in trans if t.get("id") is not None]

            rows_html = "".join(
                f"<tr><td>{t.get('fecha', '')}</td><td>{t.get('descripcion', '')}</td>"
                f"<td style='text-align:right'>${t.get('monto', 0):.2f}</td></tr>"
                for t in trans
            )

            lines = "\n".join(
                f"{i+1}. {t.get('fecha', '')} - {t.get('descripcion', '')} - ${t.get('monto', 0):.2f}"
                for i, t in enumerate(trans)
            )

            asunto = f"Pagos sin comprobante fiscal — {tipo_resumen} — {periodo}"

            body_html = f"""
<p>Estimado/a {group['name']},</p>

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

<p>Sin otro particular, saludamos atentamente.</p>""".strip()

            body_text = (
                f"Estimado/a {group['name']},\n\n"
                f"Se han detectado los siguientes pagos sin comprobante fiscal:\n\n"
                f"{lines}\n\n"
                f"Solicitamos la presentación de la documentación correspondiente a la brevedad.\n\n"
                f"Saludos."
            )

            emails.append(
                {
                    "recipient_email": group["email"],
                    "recipient_name": group["name"],
                    "subject": asunto,
                    "body_html": body_html,
                    "body_text": body_text,
                    "card_numbers": sorted(group["card_numbers"]),
                    "transaction_ids": transaction_ids,
                }
            )

        return emails

    @staticmethod
    def generate_email_content(
        transacciones_unmatched: list[dict],
        tipo_resumen: str,
        periodo: str,
        destinatario: str,
        llm_router=None,
    ) -> tuple[str, str]:
        """DEPRECATED: Use generate_emails() instead."""
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
            except LLMError:
                raise
            except Exception as e:
                logger.warning("Error al generar email con LLM, usando fallback: %s", e)

        return asunto, cuerpo_html
