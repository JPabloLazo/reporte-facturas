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
            "fecha": string | null (formato DD-MM-YYYY),
            "vencimiento": string | null (formato DD-MM-YYYY),
            "emisor": string | null,
            "cuit_emisor": string | null,
            "moneda": string | null ("ARS", "USD", etc.),
            "numero_factura": string | null,
            "cuota_numero": int | null
        }

        Reglas:
        - Si un campo no aparece en la factura, devolvé null (no inventes)
        - Si hay múltiples montos, el monto_total es el importe final
        - Para facturas de servicios USA (Apple, Google, etc.), tipo_factura = "comprobante_pago"
        - Si la fecha aparece en formato YYYY-MM-DD o DD/MM/YYYY, convertila a DD-MM-YYYY.
        - Para cuota_numero: si la factura dice 'Cuota 2/6' o 'Cuota 2 de 6', devolvé el número de cuota (ej: 2). Si no aplica, null.
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
            if "cuota_numero" in data and data["cuota_numero"] is not None:
                data["cuota_numero"] = int(data["cuota_numero"])

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
                    "cuota_numero": data.get("cuota_numero"),
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
                    "cuota_numero": None,
                }

    @staticmethod
    def extract_fields_from_images(images_base64: list[str], llm_router: LLMRouter) -> dict:
        vision_prompt = """Eres un analista visual de facturas argentinas. Analizá la imagen proporcionada y extraé los datos estructurados.

Devolvé ÚNICAMENTE un objeto JSON con estos campos (null si no se ve en la imagen):
{
  "monto_total": float | null,
  "subtotal": float | null,
  "tipo_factura": string | null,
  "fecha": string | null,
  "vencimiento": string | null,
  "emisor": string | null,
  "cuit_emisor": string | null,
  "moneda": string | null,
  "numero_factura": string | null,
  "cuota_numero": int | null
}

Reglas visuales:
- fecha y vencimiento: formato DD-MM-YYYY. Si en la imagen dice "15/01/2026", devolvé "15-01-2026".
- monto_total: buscá el IMPORTE FINAL (suele estar abajo a la derecha, junto a "Total", "Importe total" o "Neto a pagar").
- subtotal: aparece antes de IVA/impuestos. Si no se distingue, null.
- tipo_factura: letra grande en el encabezado ("A", "B", "C", etc.). Para Apple, Google, Amazon, Netflix, etc., usá "comprobante_pago".
- moneda: si ves "U$S" o "USD", devolvé "USD". Si no, "ARS".
- cuit_emisor: número de 11 dígitos, a veces con guiones. Devolvé solo dígitos (ej: "30712345678").
- cuota_numero: si la imagen muestra "Cuota 3 de 12" o "3/12", devolvé 3.
- No inventes datos. Si algo no se lee claramente, null.
- Respondé SOLO con JSON válido. Sin explicaciones, sin markdown, sin texto extra."""

        try:
            response = llm_router.extract_text_with_prompt(
                images=images_base64,
                prompt=vision_prompt,
                task_type="vision"
            )

            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
            if json_match:
                response = json_match.group(1)

            data = json.loads(response)

            if "monto_total" in data and data["monto_total"] is not None:
                data["monto_total"] = float(data["monto_total"])
            if "subtotal" in data and data["subtotal"] is not None:
                data["subtotal"] = float(data["subtotal"])
            if "cuota_numero" in data and data["cuota_numero"] is not None:
                data["cuota_numero"] = int(data["cuota_numero"])

            return {
                **data,
                "raw_response": response,
                "extraction_method": "vision_agent"
            }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Primer intento de extracción por visión falló: %s", e)
            try:
                response = llm_router.extract_text_with_prompt(
                    images=images_base64,
                    prompt=vision_prompt + "\n\nIMPORTANTE: Respondé SOLAMENTE con el JSON. Sin explicaciones, sin texto adicional, sin bloques de código markdown.",
                    task_type="vision"
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
                    "cuota_numero": data.get("cuota_numero"),
                    "raw_response": response,
                    "extraction_method": "vision_agent",
                    "_retry": True
                }
            except Exception:
                logger.error("Segundo intento de extracción por visión también falló", exc_info=True)
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
                    "cuota_numero": None,
                    "extraction_method": "vision_agent",
                }
