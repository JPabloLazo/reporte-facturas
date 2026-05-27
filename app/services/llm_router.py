from app.config import Settings
import json


class LLMRouter:
    def __init__(self, settings: Settings):
        self.settings = settings

    def _get_provider_config(self, task_type: str) -> tuple[str, str, str]:
        model_map = {
            "extraction": self.settings.model_extraction,
            "vision": self.settings.model_vision,
            "reconciliation": self.settings.model_reconciliation,
            "email": self.settings.model_email,
        }
        key_map = {
            "anthropic": self.settings.anthropic_api_key,
            "openai": self.settings.openai_api_key,
            "openrouter": self.settings.openrouter_api_key,
            "opencode": self.settings.opencode_api_key,
        }
        model = model_map.get(task_type, self.settings.model_extraction)

        provider = self.settings.default_llm_provider
        if model.startswith("claude-"):
            provider = "anthropic"
        elif model.startswith(("gpt-", "o1-", "o3-")):
            provider = "openai"
        elif provider == "anthropic" and not key_map["anthropic"]:
            provider = "openai"
        elif provider == "openai" and not key_map["openai"]:
            provider = "openrouter"

        api_key = key_map.get(provider, "")
        if not api_key:
            for p in ["anthropic", "openai", "openrouter", "opencode"]:
                if key_map[p]:
                    provider = p
                    api_key = key_map[p]
                    break

        return provider, model, api_key

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
                    raise ValueError(f"OpenRouter error: {data['error'].get('message', str(data['error']))}")
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
                    raise ValueError(f"OpenRouter error: {data['error'].get('message', str(data['error']))}")
                if "choices" not in data or not data["choices"]:
                    raise ValueError(f"OpenRouter respuesta inesperada: {str(data)[:200]}")
                return data["choices"][0]["message"]["content"]

        raise ValueError("No hay API key de LLM configurada. Andá a Configuración > Proveedores de IA y configurá al menos una.")

    def extract_with_vision(self, images: list[str], task_type: str = "vision") -> str:
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

        prompt = """Eres un extractor de transacciones de resúmenes de tarjeta de crédito de Argentina.
Analizá el resumen y extraé SOLO las transacciones de compras/pagos en formato JSON.

REGLAS:
- Fecha en formato DD/MM/AAAA
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
  {"fecha":"21/04/2026","descripcion":"MERPAGO*MELI","monto":40.00,"moneda":"ARS",
   "numero_tarjeta":"****42000","tipo_tarjeta":"AMEX",
   "cantidad_cuotas":4,"cuotas_faltantes":3,"cuota_numero":1}
]"""
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
