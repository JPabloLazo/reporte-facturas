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
            for p in ["anthropic", "openai", "openrouter"]:
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
            with httpx.Client() as http:
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

        raise ValueError("No hay API key de LLM configurada. Andá a Configuración > Proveedores de IA y configurá al menos una.")

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

        elif provider == "openrouter":
            import httpx
            with httpx.Client() as http:
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

    @staticmethod
    def _extract_json(text: str) -> str:
        """Strip markdown code blocks and extract JSON from LLM response."""
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            return json_match.group(1).strip()
        return text.strip()

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

        prompt = "Extraé de esta imagen del resumen bancario todas las transacciones en formato JSON. Cada transacción debe tener: fecha, descripcion, monto, y si aparece el número de tarjeta, también incluilo."
        content = _build_content(prompt)
        response_text = self._do_vision_call(provider, model, api_key, content)

        cleaned = self._extract_json(response_text)
        try:
            data = json.loads(cleaned)
            if isinstance(data, (list, dict)):
                return response_text  # return original in case caller needs it
        except json.JSONDecodeError:
            pass

        retry_content = _build_content(f"{prompt} IMPORTANTE: Respondé SOLO con JSON válido, sin texto adicional.")
        retry_response = self._do_vision_call(provider, model, api_key, retry_content)

        cleaned = self._extract_json(retry_response)
        try:
            data = json.loads(cleaned)
            if isinstance(data, (list, dict)):
                return retry_response
        except json.JSONDecodeError:
            return ""
