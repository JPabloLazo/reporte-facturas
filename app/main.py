import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.database import engine, Base
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.upload_dir, exist_ok=True)
    if settings.database_url.startswith("sqlite"):
        db_file = settings.database_url.replace("sqlite+aiosqlite:///", "")
        os.makedirs(os.path.dirname(db_file) or ".", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Reporte Facturas API", lifespan=lifespan)

templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DriveSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        session_id = request.cookies.get("drive_session")
        if not session_id:
            session_id = str(uuid.uuid4())
        request.state.session_id = session_id
        response = await call_next(request)
        if not request.cookies.get("drive_session"):
            response.set_cookie(
                key="drive_session",
                value=session_id,
                max_age=30*24*60*60,
                httponly=True,
                samesite="lax",
            )
        return response


app.add_middleware(DriveSessionMiddleware)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


try:
    from app.routers import config as config_router
    from app.routers import drive as drive_router
    from app.routers import process as process_router
    from app.routers import reports as reports_router
    from app.routers import upload as upload_router

    app.include_router(config_router.router, prefix="/api/config", tags=["config"])
    app.include_router(upload_router.router, prefix="/api/upload", tags=["upload"])
    app.include_router(drive_router.router, prefix="/api/drive", tags=["drive"])
    app.include_router(process_router.router, prefix="/api/process", tags=["process"])
    app.include_router(reports_router.router, prefix="/api/reports", tags=["reports"])
except ImportError:
    pass
