from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db
from app.config import settings
from app.services.drive_service import GoogleDriveService
from app.models import GoogleToken, DriveSession, Setting

router = APIRouter()


@router.get("/auth/google")
async def auth_google(request: Request, db: AsyncSession = Depends(get_db)):
    # Try DB credentials first (saved from UI), fallback to .env
    result = await db.execute(select(Setting).where(Setting.key.in_(["google_client_id", "google_client_secret"])))
    db_settings = {row.key: row.value for row in result.scalars().all()}
    client_id = db_settings.get("google_client_id", settings.google_client_id)
    client_secret = db_settings.get("google_client_secret", settings.google_client_secret)

    if not client_id or not client_secret:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Google Drive no está configurado",
                "needs_config": True,
                "message": "Para conectar Google Drive, andá a la pestaña Configuración, seguí la guía paso a paso e ingresá las credenciales de Google Cloud."
            }
        )
    redirect_uri = str(request.base_url).rstrip("/") + "/api/drive/auth/callback"
    svc = GoogleDriveService(None)
    try:
        auth_url = svc.get_auth_url(redirect_uri, client_id, client_secret)
        return {"auth_url": auth_url}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e), "needs_config": True})


@router.get("/config-status")
async def drive_config_status(db: AsyncSession = Depends(get_db)):
    """Indica si las credenciales de Google Drive están configuradas (DB + env)"""
    result = await db.execute(select(Setting).where(Setting.key.in_(["google_client_id", "google_client_secret"])))
    db_settings = {row.key: row.value for row in result.scalars().all()}
    client_id = db_settings.get("google_client_id") or settings.google_client_id
    client_secret = db_settings.get("google_client_secret") or settings.google_client_secret
    return {
        "configured": bool(client_id and client_secret),
        "connected": False,
    }

@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: str,
    db: AsyncSession = Depends(get_db),
):
    redirect_uri = str(request.base_url).rstrip("/") + "/api/drive/auth/callback"
    result = await db.execute(select(Setting).where(Setting.key.in_(["google_client_id", "google_client_secret"])))
    db_settings = {row.key: row.value for row in result.scalars().all()}
    client_id = db_settings.get("google_client_id", settings.google_client_id)
    client_secret = db_settings.get("google_client_secret", settings.google_client_secret)
    svc = GoogleDriveService(db)
    try:
        session_id = getattr(request.state, 'session_id', '')
        creds, email = await svc.handle_callback(code, redirect_uri, session_id, client_id, client_secret)
        return RedirectResponse(url="/?drive=connected")
    except Exception as e:
        error_msg = str(e).replace("'", "").replace('"', '').replace(" ", "+")
        return RedirectResponse(url=f"/?drive=error&message={error_msg}")


@router.get("/auth/check")
async def auth_check(request: Request, db: AsyncSession = Depends(get_db)):
    session_id = getattr(request.state, 'session_id', '')
    svc = GoogleDriveService(db)
    try:
        creds = await svc.get_credentials(session_id)
        email = ""
        if session_id:
            result = await db.execute(select(DriveSession).where(DriveSession.session_id == session_id))
            row = result.scalar_one_or_none()
            if row:
                email = row.email or ""
        return {"connected": creds is not None, "email": email}
    except Exception:
        return {"connected": False, "email": ""}


@router.post("/auth/disconnect")
async def auth_disconnect(request: Request, db: AsyncSession = Depends(get_db)):
    session_id = getattr(request.state, 'session_id', '')
    if session_id:
        result = await db.execute(select(DriveSession).where(DriveSession.session_id == session_id))
        row = result.scalar_one_or_none()
        if row:
            await db.delete(row)
            await db.commit()
    return {"status": "ok", "message": "Drive desconectado"}


@router.get("/status")
async def drive_status(request: Request, db: AsyncSession = Depends(get_db)):
    svc = GoogleDriveService(db)
    session_id = getattr(request.state, 'session_id', '')
    token = await svc.get_credentials(session_id)
    email = ""
    if session_id:
        result = await db.execute(select(DriveSession).where(DriveSession.session_id == session_id))
        row = result.scalar_one_or_none()
        if row:
            email = row.email or ""
    return {"connected": token is not None, "email": email}


@router.get("/folders")
async def list_drive_folders(
    year: str = Query(...),
    month: str = Query(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    svc = GoogleDriveService(db)
    session_id = getattr(request.state, 'session_id', '')
    try:
        folders = await svc.find_folders_by_year_month(session_id, year, month)
        return {"folders": folders}
    except PermissionError as e:
        return JSONResponse(status_code=403, content={"error": str(e)})


@router.get("/browse")
async def browse_drive(
    parent_id: str = Query("root"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Navegador de Drive: devuelve carpetas + preview de archivos de una carpeta"""
    svc = GoogleDriveService(db)
    session_id = getattr(request.state, 'session_id', '')
    try:
        folders = await svc.list_folders(session_id, parent_id)
        files = await svc.list_files_in_folder(session_id, parent_id)
        return {"folders": folders, "files": files}
    except PermissionError as e:
        return JSONResponse(status_code=403, content={"error": str(e)})

@router.get("/files")
async def list_drive_files(
    folder_id: str = Query(...),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    svc = GoogleDriveService(db)
    session_id = getattr(request.state, 'session_id', '')
    try:
        files = await svc.list_folder_contents(session_id, folder_id)
        return {"files": files}
    except PermissionError as e:
        return JSONResponse(status_code=403, content={"error": str(e)})
