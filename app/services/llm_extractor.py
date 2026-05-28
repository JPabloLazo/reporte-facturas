import json
import re
import logging

from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


class InvoiceExtractor:
    @staticmethod
    def extract_fields_from_markdown(markdown_text: str, llm_router: LLMRouter) -> dict:
        system_prompt = """Eres un extractor estructurado de datos de facturas argentinas. 
Recibís el texto de una factura extraído automáticamente (puede venir con ruido, tablas o saltos de línea).
Tu trabajo es analizar el texto COMPLETO y devolver ÚNICAMENTE un objeto JSON con los campos detectados.

Campos requeridos (devolvé null SOLO si el campo está realmente ausente del texto):
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

=== ESTRATEGIA DE BÚSQUEDA (seguí este orden para cada campo) ===

1. monto_total: buscá las palabras "TOTAL A PAGAR", "TOTAL:", "Total a pagar", "Importe total", "Neto a pagar", "TOTAL". Elegí el importe final (suele ser el más grande o el último). Ignorá "Total AL 2do VENCIMIENTO" o "Total con recargo" — NO son el monto total. Convertí "51.091,25" a 51091.25 y "$ 135.488,90" a 135488.90.

2. subtotal: buscá "Subtotal", "Total Consumo", "Total Cargos", "Total cargo fijo + variable", "Neto gravado", "Subtotal IVA". Es el importe ANTES de impuestos. Si no se distingue claramente del total, null.

3. tipo_factura: buscá en el encabezado letras grandes ("A", "B", "C", "M", "E"). Si el texto menciona "Consumidor Final", "IVA CONSUMIDOR FINAL" o "IVA Consumidor Final", usá "B". Si es una empresa con IVA discriminado, usá "A". Para servicios digitales extranjeros (Apple, Google, AWS, Netflix, PlayStation, Microsoft, Spotify, Meta), usá "comprobante_pago". Si no se puede determinar, null.

4. fecha: buscá "Fecha de emisión:", "Fecha:", "Fecha emisión:", "Fecha de emisión". Convertí a DD-MM-YYYY. Formatos aceptados: "DD/MM/YYYY", "YYYY-MM-DD", "DD-MM-YYYY". Ej: "16/05/2026" → "16-05-2026".

5. vencimiento: buscá "Fecha Vto", "Fecha de Vencimiento", "Vencimiento:", "Fecha Vto. CAE", "CAE:", "Vto:", "Vto. CAE", "primer vencimiento", "Total a pagar hasta el". NO uses "Próximo Vencimiento Estimado" ni "2do. Vencimiento". Este es uno de los campos MÁS importantes — revisá bien todo el texto antes de poner null.

6. emisor: buscá el nombre de la empresa en el encabezado. Ej: "Edenor", "AySA", "Telefónica", "Naturgy", "NEWTON STATION", "Agua y Saneamientos Argentinos S.A.", "Empresa Distribuidora".

7. cuit_emisor: buscá "CUIT:", "CUIT Nº", "C.U.I.T.", "CUIT". Extraé SOLO los 11 dígitos, sin guiones. Ej: "30-70956507-5" → "30709565075". Revisá bien — suele estar en el encabezado junto al emisor.

8. moneda: buscá "$", "pesos", "USD", "U$S". Default "ARS" si los montos están en pesos. Si aparece "USD" o "U$S", usá "USD".

9. numero_factura: buscá "Factura Nº:", "Nro Factura:", "Nro Serie:", "Número:", "Factura". Suele estar cerca de la fecha. Formato puede ser compuesto: "0003-01065344" o simple: "0027-34475147".

10. cuota_numero: buscá "Cuota", "cuota N/M", "N de M", "plan de pago". Si el texto menciona un plan de cuotas activo, extraé el número de cuota actual. Si no aplica, null.

=== REGLAS GENERALES ===
- Recorré TODO el texto antes de decidir que un campo es null. No te rindas rápido.
- Si encontrás múltiples fechas, usá la de "emisión" para fecha y la de "vencimiento" o "Vto" para vencimiento.
- Si el mismo campo aparece varias veces, elegí el valor más específico (ej: "Total a pagar" sobre "Total" genérico).
- Para montos: eliminá puntos de miles y convertí coma decimal a punto.
- No inventes datos. Si realmente no aparece tras buscar con las keywords indicadas, poné null.
- Respondé SOLO con el JSON válido. Sin explicaciones, sin markdown, sin texto adicional."""

        response = ""
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
        vision_prompt = """Eres un analista visual de facturas argentinas. Analizá la imagen proporcionada y extraé los datos estructurados siguiendo un método ordenado.

Devolvé ÚNICAMENTE un objeto JSON con estos campos:
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

=== MÉTODO DE ESCANEO VISUAL (seguí este orden) ===

1. Primero, identificá el TIPO de documento:
   - Factura argentina de servicios (luz, agua, gas, teléfono) → formato tabular con CUIT, fecha de emisión, vencimiento
   - Factura argentina de compra (tipo A/B/C) → encabezado con letra grande, CAE, fecha
   - Comprobante de pago extranjero (Apple, Google, PlayStation, Netflix, etc.) → sin CUIT argentino, moneda USD

2. monto_total: Recorré la imagen de arriba hacia abajo buscando el IMPORTE FINAL.
   Posiciones típicas: abajo a la derecha, última fila de una tabla, recuadro destacado.
   Keywords: "TOTAL A PAGAR", "TOTAL:", "Total a pagar", "Neto a pagar", "Importe total".
   Ignorá "Total AL 2do VENCIMIENTO" o montos con "recargo".
   Formato: "$ 135.488,90" → 135488.90.

3. subtotal: Buscá arriba del total. Keywords: "Subtotal", "Total Consumo", "Total cargo", "Neto gravado".
   Si no hay separación clara entre subtotal e impuestos, null.

4. fecha: Buscá en el ENCABEZADO o primeras líneas. Keywords: "Fecha de emisión:", "Fecha:", "Fecha emisión:".
   Formato DD-MM-YYYY. Ej: "16/05/2026" → "16-05-2026".

5. vencimiento: Buscá CERCA de la fecha de emisión o en un recuadro separado.
   Keywords: "Fecha Vto", "Fecha de Vencimiento", "Vencimiento:", "Vto:", "CAE:", "Fecha Vto. CAE",
   "primer vencimiento", "Total a pagar hasta el", "AL VENCIMIENTO".
   NO uses "2do. Vencimiento" ni "Próximo Vencimiento Estimado".
   Escaneá bien toda la imagen — este campo es crítico.

6. tipo_factura: Buscá una LETRA GRANDE en el encabezado (círculo o rectángulo): "A", "B", "C", "M", "E".
   Si no hay letra pero ves "Consumidor Final" o "IVA Consumidor Final" → "B".
   Si es un servicio digital extranjero (Apple, Google, PlayStation, Netflix, etc.) → "comprobante_pago".

7. emisor: Buscá en la parte SUPERIOR de la imagen (logo o nombre principal).
   Ej: "Edenor", "AySA", "Telefónica", "Naturgy", "NEWTON STATION", "PlayStation Store".

8. cuit_emisor: Buscá en el encabezado, cerca del emisor. Número de 11 dígitos.
   Keywords: "CUIT:", "CUIT Nº", "C.U.I.T.". Limpiá guiones: "30-70956507-5" → "30709565075".
   En comprobantes extranjeros, null (no tienen CUIT argentino).

9. moneda: "$" o "pesos" → "ARS". "USD", "U$S", "US$" → "USD". Default "ARS".

10. numero_factura: Buscá cerca del encabezado. "Factura Nº:", "Nro Factura:", "Factura:", "Número:".
    Formato: "0003-01065344" o "0027-34475147".

11. cuota_numero: Buscá "Cuota", "N de M", "plan de cuotas". Si aplica, extraé el número. null si no.

=== REGLAS GENERALES ===
- Escaneá la imagen COMPLETA antes de decidir null. No te rindas rápido.
- Si un campo aparece en varias posiciones, elegí el valor más esperado (total: abajo-derecha; emisor: arriba).
- Montos: eliminá puntos de miles, convertí coma decimal a punto.
- Fechas siempre DD-MM-YYYY. Si ves barras (/), reemplazalas por guiones (-).
- No inventes. Si no se ve claramente, null.
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
