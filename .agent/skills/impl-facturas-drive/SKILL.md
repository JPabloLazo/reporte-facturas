---
name: impl-facturas-drive
description: >
  Implementa la integración con Google Drive: OAuth 2.0 con flujo de usuario
  (no service account), listado de archivos por carpeta, y descarga a
  directorio temporal. Crea app/routes/drive.py y app/services/drive_service.py.
  Trigger: Cuando se necesita la funcionalidad de importar archivos desde Google Drive.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Se necesita conectar con Google Drive del usuario para listar/descargar archivos
- Se modifica el flujo OAuth de Drive
- Se agregan nuevos endpoints de Drive

## Critical Patterns

- **Stack**: `google-auth-oauthlib`, `google-api-python-client`
- **OAuth flujo de usuario** (NO service account): Usar `InstalledAppFlow` con redirect URI local. El usuario debe hacer login en su navegador
- **Credentials**: Almacenar token en sesión o archivo local (`token.json`). Refrescar automáticamente con `google.oauth2.credentials.Credentials`
- **Scopes**: `https://www.googleapis.com/auth/drive.readonly` (solo lectura)
- **drive_service.py**: Clase `DriveService` con métodos: `authenticate()`, `list_files(folder_id)`, `download_file(file_id, destination)`
- **Rutas**: `GET /drive/auth` (iniciar OAuth), `GET /drive/callback` (callback OAuth), `GET /drive/files?folder_id=X` (listar), `POST /drive/download` (descargar)
- **Descargas**: Usar `drive_service.files().get_media(fileId=...)` con `io.BytesIO`. Guardar en directorio temporal (`tempfile.gettempdir()`)
- **Manejo de errores**: Capturar `HttpError` de Google API. Si token expiró, redirigir a `/drive/auth`
- **Sesión**: Usar `fastapi.Session` o cookie firmada para mantener estado OAuth entre requests

## Code Examples

```python
# app/services/drive_service.py
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

class DriveService:
    def __init__(self, client_config: dict):
        self.client_config = client_config

    def get_auth_url(self, redirect_uri: str) -> str:
        flow = Flow.from_client_config(self.client_config, SCOPES)
        flow.redirect_uri = redirect_uri
        return flow.authorization_url(prompt="consent")[0]

    def fetch_token(self, code: str, redirect_uri: str) -> dict:
        flow = Flow.from_client_config(self.client_config, SCOPES)
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=code)
        return flow.credentials

    def list_files(self, folder_id: str, creds: Credentials) -> list:
        service = build("drive", "v3", credentials=creds)
        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType, size, modifiedTime)"
        ).execute()
        return results.get("files", [])

    def download_file(self, file_id: str, creds: Credentials) -> bytes:
        service = build("drive", "v3", credentials=creds)
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()
```

## Commands

```bash
pip install google-auth-oauthlib google-api-python-client
# Configurar Google Cloud Console -> Credentials -> OAuth 2.0 Client ID (Desktop app)
```

## Dependencies

- **impl-facturas-infra** (debe ejecutarse antes — estructura de `app/` debe existir)

## Resources

- `app/routes/drive.py`
- `app/services/drive_service.py`
- `app/services/__init__.py`
- `app/routes/__init__.py`
