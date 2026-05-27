import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models import Resumen, Transaccion, Factura, FacturaDatos
from app.services.conciliador import Conciliador
from app.services.drive_service import GoogleDriveService
from app.services.excel_generator import ExcelGenerator
from app.services.llm_extractor import InvoiceExtractor
from app.services.llm_router import LLMRouter
from app.services.markitdown_extractor import MarkitdownExtractor
from app.services.preview_service import PreviewService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/process")
async def process_reconciliation(
    resumen_id: int,
    carpeta_drive_id: str | None = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Resumen).where(Resumen.id == resumen_id))
    resumen = result.scalar_one_or_none()
    if not resumen:
        raise HTTPException(404, "Resumen no encontrado")

    facturas_creadas = 0
    session_id = getattr(request, 'state', None) and getattr(request.state, 'session_id', '')

    llm_router = None
    if settings.openrouter_api_key or settings.anthropic_api_key or settings.openai_api_key:
        llm_router = LLMRouter(settings)

    if carpeta_drive_id:
        drive = GoogleDriveService(db)
        files = await drive.list_folder_contents(session_id, carpeta_drive_id)
        pdf_files = [f for f in files if f.get("mimeType") == "application/pdf"]

        for f in pdf_files:
            file_bytes = await drive.download_file(session_id, f["id"])
            temp_path = f"/tmp/{f['id']}_{f['name']}"
            with open(temp_path, "wb") as fh:
                fh.write(file_bytes)

            markdown_text = MarkitdownExtractor.convert_to_markdown(temp_path)

            factura = Factura(
                drive_file_id=f["id"],
                drive_file_name=f["name"],
                periodo=resumen.periodo,
                markdown_text=markdown_text,
            )
            db.add(factura)
            await db.flush()

            extraccion = await _extraer_datos_factura(markdown_text, llm_router)
            if extraccion:
                fd = FacturaDatos(
                    factura_id=factura.id,
                    **extraccion,
                )
                db.add(fd)

            facturas_creadas += 1

    try:
        resultados = await Conciliador.conciliar(
            resumen_id=resumen_id,
            db=db,
            llm_router=llm_router,
        )
    except Exception:
        logger.exception("Error en conciliación para resumen %s", resumen_id)
        await db.rollback()
        raise HTTPException(500, "Error en el proceso de conciliación")

    matched = sum(1 for r in resultados if r.estado == "MATCHED")
    unmatched = sum(1 for r in resultados if r.estado == "UNMATCHED")

    # Load transaction details for each resultado
    trans_ids = [r.transaccion_id for r in resultados]
    trans_result = await db.execute(
        select(Transaccion).where(Transaccion.id.in_(trans_ids))
    )
    trans_map = {t.id: t for t in trans_result.scalars().all()}

    return {
        "resumen_id": resumen_id,
        "facturas_procesadas": facturas_creadas,
        "periodo": resumen.periodo,
        "resultados": [
            {
                "transaccion_id": r.transaccion_id,
                "factura_id": r.factura_id,
                "estado": r.estado,
                "confianza": r.confianza,
                "metodo": r.metodo,
                "fecha": str(trans_map[r.transaccion_id].fecha) if r.transaccion_id in trans_map else None,
                "descripcion": trans_map[r.transaccion_id].descripcion if r.transaccion_id in trans_map else None,
                "monto": trans_map[r.transaccion_id].monto if r.transaccion_id in trans_map else None,
                "numero_tarjeta": trans_map[r.transaccion_id].numero_tarjeta if r.transaccion_id in trans_map else None,
            }
            for r in resultados
        ],
        "resumen": {
            "total": len(resultados),
            "matched": matched,
            "unmatched": unmatched,
        },
    }


async def _extraer_datos_factura(markdown_text: str, llm_router) -> dict | None:
    try:
        extracted = InvoiceExtractor.extract_fields_from_markdown(markdown_text, llm_router)
        if extracted and extracted.get("numero_factura"):
            return extracted
    except Exception:
        logger.warning("Extracción LLM falló para factura", exc_info=True)
    return None


@router.post("/preview")
async def preview_facturas(
    data: dict,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    folder_id = data.get("folder_id")
    file_ids = data.get("file_ids")
    if not folder_id:
        raise HTTPException(400, "folder_id es requerido")

    session_id = getattr(request, 'state', None) and getattr(request.state, 'session_id', '')
    if not session_id:
        raise HTTPException(400, "No hay sesión activa")

    service = PreviewService(session_id, db)
    try:
        facturas, is_partial = await service.extract_preview(folder_id, file_ids)
    except PermissionError as e:
        raise HTTPException(400, str(e))

    errores = sum(1 for f in facturas if f.get("error"))

    return {
        "facturas": facturas,
        "total": len(facturas),
        "errores": errores,
        "partial": is_partial,
        "timeout": is_partial,
    }


@router.post("/save")
async def save_preview_facturas(
    data: dict,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    resumen_id = data.get("resumen_id")
    periodo = data.get("periodo", "")
    facturas = data.get("facturas", [])

    if not resumen_id:
        raise HTTPException(400, "resumen_id es requerido")
    if not facturas:
        raise HTTPException(400, "facturas es requerido")

    saved_ids = []
    errores = 0
    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    for f in facturas:
        try:
            datos = f.get("datos") or {}
            monto_total = datos.get("monto_total")
            if monto_total is not None:
                monto_total = float(monto_total)
            subtotal = datos.get("subtotal")
            if subtotal is not None:
                subtotal = float(subtotal)
            fecha = datos.get("fecha", "")
            if fecha and not date_pattern.match(str(fecha)):
                raise ValueError(f"Fecha inválida: {fecha}, debe ser YYYY-MM-DD")
            vencimiento = datos.get("vencimiento", "")
            if vencimiento and not date_pattern.match(str(vencimiento)):
                raise ValueError(f"Vencimiento inválido: {vencimiento}, debe ser YYYY-MM-DD")
            emisor = datos.get("emisor", "")
            if not emisor:
                raise ValueError("emisor no puede estar vacío")
            cuota_numero = datos.get("cuota_numero")
            if cuota_numero is not None:
                cuota_numero = int(cuota_numero)

            drive_file_id = f.get("drive_file_id", "")
            if drive_file_id:
                existing = await db.execute(
                    select(Factura).where(Factura.drive_file_id == drive_file_id)
                )
                if existing.scalar_one_or_none():
                    logger.warning("Factura con drive_file_id %s ya existe, saltando", drive_file_id)
                    errores += 1
                    continue

            # Use savepoint to isolate each factura save
            async with db.begin_nested():
                factura = Factura(
                    drive_file_id=drive_file_id,
                    drive_file_name=f.get("drive_file_name", ""),
                    periodo=periodo,
                    markdown_text=f.get("raw_text", ""),
                )
                db.add(factura)
                await db.flush()

                fd = FacturaDatos(
                    factura_id=factura.id,
                    monto_total=monto_total,
                    subtotal=subtotal,
                    tipo_factura=datos.get("tipo_factura", ""),
                    fecha=fecha,
                    vencimiento=vencimiento,
                    emisor=emisor,
                    cuit_emisor=datos.get("cuit_emisor", ""),
                    moneda=datos.get("moneda", "ARS"),
                    numero_factura=datos.get("numero_factura", ""),
                    cuota_numero=cuota_numero,
                )
                db.add(fd)
                await db.flush()

                saved_ids.append(factura.id)
        except Exception as e:
            logger.warning("Error guardando factura: %s", e)
            errores += 1

    await db.commit()

    return {
        "saved": len(saved_ids),
        "errores": errores,
        "factura_ids": saved_ids,
    }


@router.get("/preview/excel")
async def preview_excel(
    folder_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    session_id = getattr(request, 'state', None) and getattr(request.state, 'session_id', '')
    if not session_id:
        raise HTTPException(400, "No hay sesión activa")

    service = PreviewService(session_id, db)
    try:
        facturas, _ = await service.extract_preview(folder_id, None)
    except PermissionError as e:
        raise HTTPException(400, str(e))

    excel_bytes = ExcelGenerator.generate_invoices_preview_excel(facturas)

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=vista_previa_facturas.xlsx"},
    )
