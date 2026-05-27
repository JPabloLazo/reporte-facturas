import base64
import io
import logging
import os
import asyncio

from PIL import Image
from pdf2image import convert_from_bytes

from app.services.drive_service import GoogleDriveService
from app.services.markitdown_extractor import MarkitdownExtractor
from app.services.llm_extractor import InvoiceExtractor
from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


class PreviewService:
    def __init__(self, session_id: str, db):
        self.session_id = session_id
        self.db = db
        self.drive = GoogleDriveService(db)

    async def _build_llm_router(self) -> LLMRouter | None:
        from app.config import settings
        if settings.openrouter_api_key or settings.anthropic_api_key or settings.openai_api_key:
            return LLMRouter(settings)
        return None

    async def extract_preview(self, carpeta_drive_id: str, file_ids: list[str] | None = None) -> tuple[list[dict], bool]:
        llm_router = await self._build_llm_router()
        files = await self.drive.list_folder_contents(self.session_id, carpeta_drive_id)

        target_files = []
        for f in files:
            mime = f.get("mimeType", "")
            name = f.get("name", "")
            ext = os.path.splitext(name)[1].lower()
            if mime == "application/pdf" or mime.startswith("image/") or ext in IMAGE_EXTENSIONS:
                # If file_ids specified, only include selected files
                if file_ids is None or f.get("id") in file_ids:
                    target_files.append(f)

        async def procesar_archivo(f: dict) -> dict:
            try:
                file_bytes = await self.drive.download_file(self.session_id, f["id"])
                temp_path = f"/tmp/{f['id']}_{f['name']}"
                with open(temp_path, "wb") as fh:
                    fh.write(file_bytes)

                texto, metodo = MarkitdownExtractor.convert_with_fallback(temp_path)
                file_ext = os.path.splitext(f["name"])[1].lower()

                if metodo in ("vision", "vision_fallback"):
                    images_base64 = []
                    if file_ext in IMAGE_EXTENSIONS:
                        img = Image.open(temp_path)
                        buffer = io.BytesIO()
                        img.convert("RGB").save(buffer, format="JPEG", quality=60)
                        images_base64.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
                    else:
                        pages = convert_from_bytes(file_bytes, dpi=150)
                        pages = pages[-3:]  # Keep last 3 pages (totals)
                        for page in pages:
                            buffer = io.BytesIO()
                            page.convert("RGB").save(buffer, format="JPEG", quality=60)
                            images_base64.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))

                    if images_base64 and llm_router:
                        datos = await asyncio.to_thread(
                            InvoiceExtractor.extract_fields_from_images,
                            images_base64,
                            llm_router,
                        )
                    else:
                        datos = None
                elif metodo == "markitdown" and llm_router:
                    datos = await asyncio.to_thread(
                        InvoiceExtractor.extract_fields_from_markdown,
                        texto,
                        llm_router,
                    )
                else:
                    datos = None

                return {
                    "drive_file_id": f["id"],
                    "drive_file_name": f["name"],
                    "file_extension": file_ext,
                    "extraction_method": metodo,
                    "raw_text": texto,
                    "datos": datos,
                    "error": None,
                }
            except Exception as e:
                logger.warning("Error procesando %s: %s", f.get("name", ""), e, exc_info=True)
                return {
                    "drive_file_id": f.get("id", ""),
                    "drive_file_name": f.get("name", ""),
                    "file_extension": os.path.splitext(f.get("name", ""))[1].lower(),
                    "extraction_method": "error",
                    "raw_text": "",
                    "datos": None,
                    "error": str(e),
                }

        if not target_files:
            return [], False

        # Process PDFs first (markdown candidates), then images (vision)
        markdown_candidates = [
            f for f in target_files
            if os.path.splitext(f.get("name", ""))[1].lower() == ".pdf"
        ]
        vision_candidates = [
            f for f in target_files
            if os.path.splitext(f.get("name", ""))[1].lower() != ".pdf"
        ]
        sorted_files = markdown_candidates + vision_candidates

        # Parallel processing with concurrency limit
        sem = asyncio.Semaphore(4)

        async def procesar_con_semaphore(f: dict) -> dict:
            async with sem:
                try:
                    return await asyncio.wait_for(procesar_archivo(f), timeout=120)
                except asyncio.TimeoutError:
                    logger.warning("Timeout procesando %s", f.get("name", ""))
                    return {
                        "drive_file_id": f.get("id", ""),
                        "drive_file_name": f.get("name", ""),
                        "file_extension": os.path.splitext(f.get("name", ""))[1].lower(),
                        "extraction_method": "error",
                        "raw_text": "",
                        "datos": None,
                        "error": "Timeout: el archivo excedió el límite de 120 segundos",
                    }

        tasks = [procesar_con_semaphore(f) for f in sorted_files]
        resultados = await asyncio.gather(*tasks)
        return resultados, False
