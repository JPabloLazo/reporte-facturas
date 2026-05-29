from app.config import Settings, IA_PROFILES, DEFAULT_IA_PROFILE
import json


class LLMError(Exception):
    """Error estructurado de una API de LLM."""
    def __init__(self, type: str, message: str, provider: str = "openrouter"):
        self.type = type
        self.message = message
        self.provider = provider
        super().__init__(self.message)

ERROR_SUGGESTIONS = {
    "insufficient_credits": "No hay saldo disponible en OpenRouter. Por favor, recargá tu cuenta para continuar.",
    "rate_limit": "OpenRouter está recibiendo muchas solicitudes. Esperá unos segundos e intentá de nuevo.",
    "model_unavailable": "El modelo seleccionado no está disponible. Probá con otro perfil en Configuración.",
    "network_error": "No se pudo conectar con OpenRouter. Verificá tu conexión a internet.",
    "unknown": "Ocurrió un error inesperado con OpenRouter. Si persiste, probá con otro perfil.",
}


class LLMRouter:
    _PROMPT_GENERIC = """Eres un extractor de transacciones de resúmenes de tarjeta de crédito de Argentina.
Analizá el resumen y extraé SOLO las transacciones de compras/pagos en formato JSON.

REGLAS:
- Fecha en formato DD-MM-AAAA
- Monto como número decimal (sin puntos de miles, coma decimal → punto)
- "CR" (crédito/pago) → monto NEGATIVO
- "DB" (débito/compra) → monto POSITIVO
- Moneda: "ARS" o "USD"
- tipo_tarjeta: detectar del encabezado (AMEX, VISA, Mastercard, etc.)
- Si tiene cuotas (ej: "1/6", "1 de 6", "cuota 1"):
  - cantidad_cuotas: número total de cuotas
  - cuotas_faltantes: cuántas faltan pagar
  - cuota_numero: número de esta cuota
- Ignorar totales, subtotales, resúmenes, saldos y gracias por su pago

Formato:
[
  {"fecha":"21-04-2026","descripcion":"MERPAGO*MELI","monto":40.00,"moneda":"ARS",
   "numero_tarjeta":"****42000","tipo_tarjeta":"AMEX",
   "cantidad_cuotas":4,"cuotas_faltantes":3,"cuota_numero":1}
]"""

    _PROMPT_AMEX = """Eres un extractor de transacciones de resúmenes de tarjeta AMEX de Argentina.
Analizá el resumen y extraé SOLO las transacciones de compras/pagos en formato JSON.

Formato del resumen AMEX:
- Tabla con columnas: Fecha | Descripción | Importe $ | Importe U$S
- Buscar "Total en Pesos" y "Total en Dólares" para identificar la moneda
- Cuotas aparecen como "1/6", "2/6" etc.
- Tarjeta: buscar "Titular", "Tarjeta", "Número" en el encabezado

REGLAS:
- Fecha en formato DD-MM-AAAA
- Monto como número decimal (sin puntos de miles, coma decimal → punto)
- Moneda: "ARS" o "USD" según la columna del importe
- CR (crédito/pago) → monto NEGATIVO
- DB (débito/compra) → monto POSITIVO
- tipo_tarjeta: "AMEX"
- Si tiene cuotas (ej: "1/6", "2/6"):
  - cantidad_cuotas: número total de cuotas
  - cuotas_faltantes: cuántas faltan pagar
  - cuota_numero: número de esta cuota
- Ignorar totales, subtotales, resúmenes, saldos, fees y "gracias por su pago"

Formato JSON:
[
  {"fecha":"21-04-2026","descripcion":"MERPAGO*MELI","monto":40.00,"moneda":"ARS",
   "numero_tarjeta":"****2000","tipo_tarjeta":"AMEX",
   "cantidad_cuotas":6,"cuotas_faltantes":5,"cuota_numero":1}
]"""

    _PROMPT_VISA = """Eres un extractor de transacciones de resúmenes de tarjeta VISA de Argentina.
Analizá el resumen y extraé SOLO las transacciones de compras/pagos en formato JSON.

Formato del resumen VISA:
- Layout de 2 columnas: débito (izquierda), crédito (derecha)
- Fechas de liquidación vs. fecha de compra (usar la de compra)
- "CR" = crédito/pago → monto NEGATIVO
- "DB" = débito/compra → monto POSITIVO
- Cuotas: "1/3", "cuota 1 de 3", etc.

REGLAS:
- Fecha en formato DD-MM-AAAA
- Monto como número decimal (sin puntos de miles, coma decimal → punto)
- Moneda: "ARS" o "USD"
- tipo_tarjeta: "VISA"
- Buscar "Nro. de Tarjeta" o "Tarjeta" para el número
- Si tiene cuotas (ej: "1/3", "cuota 1 de 3"):
  - cantidad_cuotas: número total de cuotas
  - cuotas_faltantes: cuántas faltan pagar
  - cuota_numero: número de esta cuota
- Ignorar totales, subtotales, resúmenes, saldos y gracias por su pago

Formato JSON:
[
  {"fecha":"21-04-2026","descripcion":"MERPAGO*MELI","monto":40.00,"moneda":"ARS",
   "numero_tarjeta":"****2000","tipo_tarjeta":"VISA",
   "cantidad_cuotas":3,"cuotas_faltantes":2,"cuota_numero":1}
]"""

    _PROMPT_MASTERCARD = """Eres un extractor de transacciones de resúmenes de tarjeta Mastercard de Argentina.
Analizá el resumen y extraé SOLO las transacciones de compras/pagos en formato JSON.

Formato del resumen Mastercard:
- Tabla de consumos con columna de cuotas
- Layout similar a VISA pero con formato propio
- Totales en pesos al final (ignorar)
- Cuotas: "1/3", "cuota 1", etc.

REGLAS:
- Fecha en formato DD-MM-AAAA
- Monto como número decimal (sin puntos de miles, coma decimal → punto)
- Moneda: "ARS" o "USD"
- tipo_tarjeta: "MASTERCARD"
- CR (crédito/pago) → monto NEGATIVO
- DB (débito/compra) → monto POSITIVO
- Si tiene cuotas:
  - cantidad_cuotas: número total de cuotas
  - cuotas_faltantes: cuántas faltan pagar
  - cuota_numero: número de esta cuota
- Ignorar totales, subtotales, resúmenes, saldos, fees y "gracias por su pago"

Formato JSON:
[
  {"fecha":"21-04-2026","descripcion":"MERPAGO*MELI","monto":40.00,"moneda":"ARS",
   "numero_tarjeta":"****2000","tipo_tarjeta":"MASTERCARD",
   "cantidad_cuotas":3,"cuotas_faltantes":2,"cuota_numero":1}
]"""

    def __init__(self, settings: Settings):
        self.settings = settings

    def _get_card_prompt(self, card_type: str) -> str:
        prompts = {
            "AMEX": self._PROMPT_AMEX,
            "VISA": self._PROMPT_VISA,
            "MASTERCARD": self._PROMPT_MASTERCARD,
        }
        return prompts.get(card_type, self._PROMPT_GENERIC)

    def _get_model_for_task(self, task_type: str) -> str:
        """Resuelve el modelo para una tarea según el perfil activo."""
        profile = getattr(self.settings, "ia_profile", DEFAULT_IA_PROFILE) or DEFAULT_IA_PROFILE
        if profile not in IA_PROFILES:
            profile = DEFAULT_IA_PROFILE
        return IA_PROFILES[profile].get(task_type, IA_PROFILES[DEFAULT_IA_PROFILE]["extraction"])

    @staticmethod
    def _parse_openrouter_error(error_data: dict) -> LLMError:
        """Parsea el error de OpenRouter y devuelve un LLMError tipificado."""
        msg = (error_data.get("message") or "").lower()
        if any(kw in msg for kw in ["insufficient", "credit", "balance", "funds"]):
            return LLMError("insufficient_credits", str(error_data.get("message", "")))
        if any(kw in msg for kw in ["rate", "too many", "429"]):
            return LLMError("rate_limit", str(error_data.get("message", "")))
        if any(kw in msg for kw in ["not found", "not available", "does not exist", "not supported"]):
            return LLMError("model_unavailable", str(error_data.get("message", "")))
        return LLMError("unknown", str(error_data.get("message", "")))

    def _get_provider_config(self, task_type: str) -> tuple[str, str, str]:
        model = self._get_model_for_task(task_type)
        api_key = self.settings.openrouter_api_key
        if not api_key:
            raise ValueError("No hay API key de OpenRouter configurada. Configurá OPENROUTER_API_KEY en .env")
        return "openrouter", model, api_key

    def chat(self, messages: list, task_type: str = "extraction", max_tokens: int = 2000) -> str:
        provider, model, api_key = self._get_provider_config(task_type)
        if not api_key:
            raise ValueError(f"No hay API key configurada para {provider}. Andá a Configuración > Proveedores de IA.")

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens
            )
            return resp.content[0].text

        elif provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )
            return resp.choices[0].message.content

        elif provider == "openrouter":
            import httpx
            with httpx.Client(timeout=120) as http:
                resp = http.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                    }
                )
                data = resp.json()
                if "error" in data:
                    raise self._parse_openrouter_error(data["error"])
                if "choices" not in data or not data["choices"]:
                    raise ValueError(f"OpenRouter respuesta inesperada: {str(data)[:200]}")
                return data["choices"][0]["message"]["content"]

        elif provider == "opencode":
            import httpx
            with httpx.Client(timeout=300) as http:
                resp = http.post(
                    "https://opencode.ai/zen/go/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                    },
                    timeout=300
                )
                data = resp.json()
                if "error" in data:
                    raise ValueError(f"OpenCode error: {data['error'].get('message', str(data['error']))}")
                if "choices" not in data or not data["choices"]:
                    raise ValueError(f"OpenCode respuesta inesperada: {str(data)[:200]}")
                return data["choices"][0]["message"]["content"]

        raise ValueError("No hay API key de LLM configurada. Andá a Configuración > Proveedores de IA y configurá al menos una.")

    def extract_text_with_prompt(self, images: list[str], prompt: str, task_type: str = "vision") -> str:
        provider, model, api_key = self._get_provider_config(task_type)
        if not api_key:
            raise ValueError(f"No hay API key configurada para {provider}.")

        content = [{"type": "text", "text": prompt}]
        for img in images:
            if provider == "anthropic":
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": img}
                })
            else:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img}"}
                })

        return self._do_vision_call(provider, model, api_key, content)

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown code blocks and extract JSON from LLM response."""
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            return json_match.group(1).strip()
        return text.strip()

    def _do_vision_call(self, provider: str, model: str, api_key: str, content: list) -> str:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                max_tokens=2000
            )
            return resp.content[0].text

        elif provider == "openai":
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            return resp.choices[0].message.content

        elif provider == "opencode":
            import httpx
            with httpx.Client(timeout=300) as http:
                resp = http.post(
                    "https://opencode.ai/zen/go/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": content}],
                        "max_tokens": 3000,
                    },
                    timeout=300
                )
                data = resp.json()
                if "error" in data:
                    raise ValueError(f"OpenCode error: {data['error'].get('message', str(data['error']))}")
                if "choices" not in data or not data["choices"]:
                    raise ValueError(f"OpenCode respuesta inesperada: {str(data)[:200]}")
                return data["choices"][0]["message"]["content"]

        elif provider == "openrouter":
            import httpx
            with httpx.Client(timeout=120) as http:
                resp = http.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": content}],
                        "max_tokens": 2000,
                    },
                    timeout=120
                )
                data = resp.json()
                if "error" in data:
                    raise self._parse_openrouter_error(data["error"])
                if "choices" not in data or not data["choices"]:
                    raise ValueError(f"OpenRouter respuesta inesperada: {str(data)[:200]}")
                return data["choices"][0]["message"]["content"]

        raise ValueError("No hay API key de LLM configurada. Andá a Configuración > Proveedores de IA y configurá al menos una.")

    def extract_with_vision(self, images: list[str], task_type: str = "vision", card_type: str = "GENERIC") -> str:
        provider, model, api_key = self._get_provider_config(task_type)
        if not api_key:
            raise ValueError(f"No hay API key configurada para {provider}. Andá a Configuración > Proveedores de IA.")

        def _build_content(prompt_text: str) -> list:
            content = [{"type": "text", "text": prompt_text}]
            for img in images:
                if provider == "anthropic":
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": img}
                    })
                else:
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img}"}
                    })
            return content

        prompt = self._get_card_prompt(card_type)
        content = _build_content(prompt)

        # First attempt with retry on API errors
        for intento in range(2):
            try:
                response_text = self._do_vision_call(provider, model, api_key, content)
            except ValueError as e:
                if intento == 0:
                    continue  # retry once on API error
                return ""

            cleaned = self._extract_json(response_text)
            try:
                data = json.loads(cleaned)
                if isinstance(data, (list, dict)):
                    return response_text
            except json.JSONDecodeError:
                if intento == 0:
                    continue  # retry once on JSON error
            break

        # Second attempt with stricter prompt
        retry_content = _build_content(f"{prompt} IMPORTANTE: Respondé SOLO con JSON válido, sin texto adicional.")
        for intento in range(2):
            try:
                retry_response = self._do_vision_call(provider, model, api_key, retry_content)
            except ValueError:
                if intento == 0:
                    continue
                return ""

            cleaned = self._extract_json(retry_response)
            try:
                data = json.loads(cleaned)
                if isinstance(data, (list, dict)):
                    return retry_response
            except json.JSONDecodeError:
                if intento == 0:
                    continue
            break

        return ""

    def count_transactions(self, images: list[str], card_type: str = "GENERIC") -> int | None:
        """Count real transactions in images via LLM. Returns count or None on failure.
        
        Procesa una imagen a la vez para compatibilidad con proveedores que no soportan
        múltiples imágenes (ej: OpenCode/qwen3.6-plus). La suma se hace en upload.py
        con asyncio.gather para paralelismo.
        """
        result = None
        for img in images:
            try:
                prompt = self._get_card_prompt(card_type)
                count_instruction = """

INSTRUCCIÓN ADICIONAL:
AHORA NO EXTRAIGAS NADA. Solo contá cuántas transacciones REALES hay en ESTA PÁGINA.

Una transacción REAL es cualquier línea que represente:
- Una compra, pago, débito, o cargo
- Una cuota de una compra
- Un crédito o pago (CR)

NO cuentes:
- Saldos anteriores ("SALDO ANTERIOR")
- Totales, subtotales, resúmenes
- Encabezados de tabla, números de página
- "Gracias por su pago" o mensajes similares
- Fees o comisiones de mantenimiento

Respondé SOLO con el número entero. Ejemplo: 5"""
                page_result = self.extract_text_with_prompt([img], prompt + count_instruction, task_type="vision")
                cleaned = page_result.strip().strip('`').strip()
                import re
                match = re.search(r'\d+', cleaned)
                if match:
                    count = int(match.group())
                    if result is None:
                        result = 0
                    result += count
            except Exception:
                continue
        return result
