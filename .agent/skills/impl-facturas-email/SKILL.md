---
name: impl-facturas-email
description: >
  Implementa el envío de emails con resúmenes de facturas: generación de
  contenido vía LLM (Anthropic/OpenAI/Llama configurable), envío SMTP
  configurable, y lógica de destinatarios (AMEX → solo responsable,
  VISA → responsable + usuario de tarjeta). Crea
  app/services/email_sender.py y app/services/email_generator.py.
  Trigger: Cuando se necesita enviar emails con resúmenes de facturas a usuarios.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Se necesita enviar emails con resúmenes de facturas procesadas
- Se modifica el contenido, tono, o destinatarios del email
- Se configura un nuevo servidor SMTP

## Critical Patterns

- **Stack**: `smtplib` (envío SMTP), `email.mime` (construcción de mensajes)
- **email_generator.py**: Función `generar_contenido_email(datos_factura: dict, llm_router: LLMRouter, modelo: str) -> dict`
  - Usar LLM para generar: `asunto` (string corto, profesional), `cuerpo_html` (HTML con Tailwind inline), `cuerpo_texto` (versión texto plano)
  - Prompt al LLM: "Generá un email profesional y estricto para el responsable de {empresa}. La factura {tipo} por ${monto} con vencimiento {vencimiento} debe ser pagada. {Detalle de transacciones}. Tono: formal, firme pero respetuoso."
  - Retornar dict con `asunto`, `cuerpo_html`, `cuerpo_texto`
- **email_sender.py**: Clase `EmailSender` con:
  - Constructor: `__init__(self, smtp_host, smtp_port, smtp_user, smtp_password, use_tls=True)`
  - Método `enviar(destinatarios: list[str], asunto: str, cuerpo_html: str, cuerpo_texto: str, attachments: list[dict] = None)`
  - Attachments opcionales: PDF del resumen o Excel de no conciliados. Cada attachment es `{"filename": str, "data": bytes, "mime": str}`
- **Lógica de destinatarios**:
  - Factura AMEX: email solo al responsable (campo `responsable_email` de la config)
  - Factura VISA: email al responsable + email del usuario de esa tarjeta (campo `usuario_email` de la tarjeta específica)
- **Manejo de errores**: Si SMTP falla, loguear error y retornar `{"enviado": False, "error": str}`. No reintentar automáticamente
- **Config SMTP**: Leer de `Settings` en `config.py`: `smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `smtp_use_tls`
- **HTML email**: Debe ser autocontenido (sin dependencias externas). Usar `<table>` para layout, estilos inline

## Code Examples

```python
# app/services/email_sender.py
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

class EmailSender:
    def __init__(self, host: str, port: int, user: str, password: str, use_tls: bool = True):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls

    def enviar(self, destinatarios: list[str], asunto: str,
               cuerpo_html: str, cuerpo_texto: str,
               attachments: list[dict] = None) -> dict:
        msg = MIMEMultipart("alternative")
        msg["From"] = self.user
        msg["To"] = ", ".join(destinatarios)
        msg["Subject"] = asunto
        msg.attach(MIMEText(cuerpo_texto, "plain"))
        msg.attach(MIMEText(cuerpo_html, "html"))
        if attachments:
            for att in attachments:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(att["data"])
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{att["filename"]}"')
                msg.attach(part)
        try:
            server = smtplib.SMTP(self.host, self.port)
            if self.use_tls:
                server.starttls()
            server.login(self.user, self.password)
            server.sendmail(self.user, destinatarios, msg.as_string())
            server.quit()
            return {"enviado": True}
        except Exception as e:
            return {"enviado": False, "error": str(e)}
```

## Commands

```bash
pip install smtplib  # viene en stdlib de Python
# Configurar SMTP en Settings (smtp_host, smtp_port, smtp_user, smtp_password)
```

## Dependencies

- **impl-facturas-infra** (debe ejecutarse antes — `app/config.py` con settings SMTP)
- **impl-facturas-extraccion** (debe ejecutarse antes — `llm_router` para generar contenido)

## Resources

- `app/services/email_generator.py`
- `app/services/email_sender.py`
- `app/services/__init__.py`
