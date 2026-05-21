import json
import re
import logging

from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class InvoiceExtractor:
    @staticmethod
    def extract_fields_from_markdown(markdown_text: str, llm_router: LLMRouter) -> dict:
        system_prompt = """Eres un extractor de datos de facturas argentinas. 
        Dado el texto de una factura en formato Markdown, extraé los siguientes campos y devolvelos como JSON:

        {
            "monto_total": float | null,
            "subtotal": float | null,
            "tipo_factura": string | null,
            "fecha": string | null (formato YYYY-MM-DD),
            "vencimiento": string | null (formato YYYY-MM-DD),
            "emisor": string | null,
            "cuit_emisor": string | null,
            "moneda": string | null ("ARS", "USD", etc.),
            "numero_factura": string | null
        }

        Reglas:
        - Si un campo no aparece en la factura, devolvé null (no inventes)
        - Si hay múltiples montos, el monto_total es el importe final
        - Para facturas de servicios USA (Apple, Google, etc.), tipo_factura = "comprobante_pago"
        - Solo devolvé el JSON, sin texto adicional"""

        try:
            response = llm_router.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extraé los datos de esta factura:\n\n{markdown_text}"}
                ],
                task_type="extraction",
                max_tokens=1000
            )

            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
            if json_match:
                response = json_match.group(1)

            data = json.loads(response)

            if "monto_total" in data and data["monto_total"] is not None:
                data["monto_total"] = float(data["monto_total"])
            if "subtotal" in data and data["subtotal"] is not None:
                data["subtotal"] = float(data["subtotal"])

            return {
                **data,
                "raw_response": response
            }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Primer intento de extracción falló: %s", e)
            try:
                response = llm_router.chat(
                    messages=[
                        {"role": "system", "content": system_prompt + "\n\nIMPORTANTE: Respondé SOLAMENTE con el JSON. Sin explicaciones, sin texto adicional, sin bloques de código markdown."},
                        {"role": "user", "content": f"Extraé los datos de esta factura y devolvé SOLO el JSON:\n\n{markdown_text}"}
                    ],
                    task_type="extraction",
                    max_tokens=1000
                )
                response = response.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                data = json.loads(response)
                return {
                    "monto_total": float(data["monto_total"]) if data.get("monto_total") else None,
                    "subtotal": float(data["subtotal"]) if data.get("subtotal") else None,
                    "tipo_factura": data.get("tipo_factura"),
                    "fecha": data.get("fecha"),
                    "vencimiento": data.get("vencimiento"),
                    "emisor": data.get("emisor"),
                    "cuit_emisor": data.get("cuit_emisor"),
                    "moneda": data.get("moneda"),
                    "numero_factura": data.get("numero_factura"),
                    "raw_response": response,
                    "_retry": True
                }
            except Exception:
                logger.error("Segundo intento de extracción también falló", exc_info=True)
                return {
                    "error": "invalid_json",
                    "raw": response[:500],
                    "monto_total": None,
                    "subtotal": None,
                    "tipo_factura": None,
                    "fecha": None,
                    "vencimiento": None,
                    "emisor": None,
                    "cuit_emisor": None,
                    "moneda": None,
                    "numero_factura": None,
                }
