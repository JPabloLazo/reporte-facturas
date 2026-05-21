---
name: impl-facturas-extraccion
description: >
  Implementa el pipeline de extracción estructurada de facturas: markitdown
  para convertir PDFs/imágenes a Markdown (local, sin gasto de tokens), router
  de LLM que selecciona proveedor según configuración del usuario
  (Anthropic/OpenAI/OpenRouter), y extractor que obtiene campos estructurados
  desde Markdown. Crea app/services/markitdown_extractor.py,
  app/services/llm_extractor.py, y app/services/llm_router.py.
  Trigger: Cuando se necesita extraer campos estructurados de facturas usando LLM.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Se necesita convertir PDFs/imágenes a Markdown
- Se necesita enviar prompts a LLM para extracción estructurada
- Se agrega soporte para un nuevo proveedor de LLM (Anthropic, OpenAI, OpenRouter)
- Se modifican los campos a extraer de las facturas

## Critical Patterns

- **Stack**: `markitdown` (conversión local PDF/Markdown), `httpx` (llamadas API), `anthropic` (SDK Claude), `openai` (SDK OpenAI)
- **markitdown_extractor.py**: Función `convert_to_markdown(file_path: str) -> str`. Usa markitdown para convertir PDFs e imágenes a Markdown. Sin costo de tokens (procesamiento local)
- **llm_router.py**: Clase `LLMRouter` que selecciona proveedor según config del usuario:
  - `anthropic`: Usa SDK `anthropic` + API key de Settings
  - `openai`: Usa SDK `openai` + API key
  - `openrouter`: Usa `httpx` a `https://openrouter.ai/api/v1/chat/completions` + API key
  - Método `chat(messages, model, max_tokens) -> str` unificado
  - Método `extract_with_vision(image_base64: str, model: str) -> str` para fallback de pdf_parser
- **llm_extractor.py**: Función `extract_fields_from_markdown(markdown: str, llm_router: LLMRouter) -> dict`
  - Prompt estructurado pidiendo JSON con campos: `monto_total`, `subtotal`, `tipo_factura` (A/B/C/comprobante_pago), `fecha`, `vencimiento`, `emisor`, `CUIT`, `moneda`, `numero_factura`
  - Validar que el LLM devuelva JSON válido. Si falla, reintentar 1 vez con prompt más explícito
  - Retornar dict con campos extraídos + `raw_response` (el texto original del LLM)
- **Campos opcionales**: Ningún campo debe ser obligatorio. Si el LLM no puede determinar un valor, retornar `null`
- **Manejo de errores**: Si markitdown falla, loguear warning y retornar string vacío. Si LLM retorna JSON inválido, retornar `{"error": "invalid_json", "raw": respuesta}`

## Code Examples

```python
# app/services/llm_router.py
import httpx
from anthropic import Anthropic
from openai import OpenAI

class LLMRouter:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key = api_key

    def chat(self, messages: list, model: str, max_tokens: int = 2000) -> str:
        if self.provider == "anthropic":
            client = Anthropic(api_key=self.api_key)
            resp = client.messages.create(model=model, messages=messages, max_tokens=max_tokens)
            return resp.content[0].text
        elif self.provider == "openai":
            client = OpenAI(api_key=self.api_key)
            resp = client.chat.completions.create(model=model, messages=messages, max_tokens=max_tokens)
            return resp.choices[0].message.content
        elif self.provider == "openrouter":
            with httpx.Client() as http:
                resp = http.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": model, "messages": messages, "max_tokens": max_tokens}
                )
                return resp.json()["choices"][0]["message"]["content"]
```

## Commands

```bash
pip install markitdown anthropic openai httpx
```

## Dependencies

- **impl-facturas-infra** (debe ejecutarse antes — `app/config.py` con settings de API keys, `app/models.py`)

## Resources

- `app/services/markitdown_extractor.py`
- `app/services/llm_extractor.py`
- `app/services/llm_router.py`
- `app/services/__init__.py`
