import io
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import select

from app.config import settings
from app.models import GoogleToken, DriveSession

SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

PDF_MIME = "application/pdf"
IMAGE_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
    "image/bmp",
}


class GoogleDriveService:
    def __init__(self, db_session):
        self.db = db_session

    async def get_credentials(self, session_id: str | None = None) -> Credentials | None:
        if not session_id:
            return None
        result = await self.db.execute(
            select(DriveSession).where(DriveSession.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        if not row or not row.token_json:
            return None
        creds = Credentials.from_authorized_user_info(json.loads(row.token_json), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            await self.save_credentials(session_id, row.email, creds)
        return creds

    async def save_credentials(self, session_id: str, email: str, credentials: Credentials):
        result = await self.db.execute(
            select(DriveSession).where(DriveSession.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        token_json = credentials.to_json()
        if row:
            row.token_json = token_json
            if email:
                row.email = email
        else:
            self.db.add(DriveSession(
                session_id=session_id,
                email=email,
                token_json=token_json,
            ))
        await self.db.commit()

    def _build_client_config(
        self, client_id: str | None = None, client_secret: str | None = None
    ) -> dict:
        if not client_id or not client_secret:
            client_id = settings.google_client_id
            client_secret = settings.google_client_secret
        if not client_id or not client_secret:
            raise ValueError(
                "Google Drive no está configurado. "
                "Configurá google_client_id y google_client_secret en Settings."
            )
        return {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

    def get_auth_url(self, redirect_uri: str, client_id: str | None = None, client_secret: str | None = None) -> str:
        client_config = self._build_client_config(client_id, client_secret)
        flow = Flow.from_client_config(client_config, SCOPES)
        flow.redirect_uri = redirect_uri
        auth_url, _ = flow.authorization_url(prompt="consent")
        return auth_url

    async def _get_email_from_credentials(self, credentials: Credentials) -> str:
        try:
            if hasattr(credentials, 'id_token') and credentials.id_token:
                import base64, json
                parts = credentials.id_token.split('.')
                if len(parts) >= 2:
                    payload = parts[1]
                    payload += '=' * (4 - len(payload) % 4)
                    decoded = json.loads(base64.b64decode(payload))
                    email = decoded.get('email', '')
                    if email:
                        return email
        except Exception:
            pass
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v2/userinfo",
                    headers={"Authorization": f"Bearer {credentials.token}"}
                )
                if resp.status_code == 200:
                    return resp.json().get("email", "")
        except Exception:
            pass
        return "desconocido@email.com"

    async def handle_callback(self, auth_code: str, redirect_uri: str, session_id: str, client_id: str | None = None, client_secret: str | None = None) -> tuple[Credentials, str]:
        client_config = self._build_client_config(client_id, client_secret)
        flow = Flow.from_client_config(client_config, SCOPES)
        flow.redirect_uri = redirect_uri
        flow.fetch_token(code=auth_code)
        creds = flow.credentials
        email = await self._get_email_from_credentials(creds)
        await self.save_credentials(session_id, email, creds)
        return creds, email

    async def list_files(self, session_id: str, parent_id: str | None = None) -> list[dict]:
        creds = await self._require_credentials(session_id)
        service = build("drive", "v3", credentials=creds)
        mime_filter = " or ".join(
            [f"mimeType = '{PDF_MIME}'"]
            + [f"mimeType = '{m}'" for m in IMAGE_MIMES]
        )
        query_parts = [f"({mime_filter})", "trashed = false"]
        if parent_id:
            query_parts.append(f"'{parent_id}' in parents")
        else:
            query_parts.append("'root' in parents")
        query = " and ".join(query_parts)
        results = (
            service.files()
            .list(
                q=query,
                fields="files(id, name, mimeType, size, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return results.get("files", [])

    async def find_folders_by_year_month(
        self, session_id: str, year: str, month: str
    ) -> list[str]:
        creds = await self._require_credentials(session_id)
        service = build("drive", "v3", credentials=creds)
        year_query = (
            f"name = '{year}' and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        year_results = (
            service.files()
            .list(q=year_query, fields="files(id, name)")
            .execute()
        )
        year_folders = year_results.get("files", [])
        if not year_folders:
            return []
        folder_ids = []
        for yf in year_folders:
            month_query = (
                f"name = '{month}' and "
                f"'{yf['id']}' in parents and "
                "mimeType = 'application/vnd.google-apps.folder' and "
                "trashed = false"
            )
            month_results = (
                service.files()
                .list(q=month_query, fields="files(id, name)")
                .execute()
            )
            for mf in month_results.get("files", []):
                folder_ids.append(mf["id"])
        return folder_ids

    async def download_file(self, session_id: str, file_id: str) -> bytes:
        creds = await self._require_credentials(session_id)
        service = build("drive", "v3", credentials=creds)
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    async def list_folder_contents(self, session_id: str, folder_id: str) -> list[dict]:
        creds = await self._require_credentials(session_id)
        service = build("drive", "v3", credentials=creds)
        query = (
            f"'{folder_id}' in parents and "
            "mimeType != 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        results = (
            service.files()
            .list(
                q=query,
                fields="files(id, name, mimeType, size, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return results.get("files", [])

    async def list_folders(self, session_id: str, parent_id: str = "root") -> list[dict]:
        """Lista SOLO subcarpetas de un parent (para navegación)"""
        creds = await self._require_credentials(session_id)
        service = build("drive", "v3", credentials=creds)
        query = (
            f"'{parent_id}' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        results = (
            service.files()
            .list(
                q=query,
                fields="files(id, name, mimeType, createdTime)",
                orderBy="name",
            )
            .execute()
        )
        return results.get("files", [])

    async def list_files_in_folder(self, session_id: str, folder_id: str, preview: bool = True) -> list[dict]:
        """Lista todos los archivos dentro de una carpeta (sin subcarpetas)"""
        creds = await self._require_credentials(session_id)
        service = build("drive", "v3", credentials=creds)
        query = (
            f"'{folder_id}' in parents and "
            "mimeType != 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        results = (
            service.files()
            .list(
                q=query,
                fields="files(id, name, mimeType, size, modifiedTime)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
        return results.get("files", [])

    async def _require_credentials(self, session_id: str) -> Credentials:
        creds = await self.get_credentials(session_id)
        if not creds:
            raise PermissionError(
                "No hay token de Google Drive para esta sesión. Conectá Drive primero."
            )
        return creds
