import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.models import Resumen, Transaccion, Factura, FacturaDatos
from app.services.conciliador import Conciliador
from app.services.drive_service import GoogleDriveService
from app.services.markitdown_extractor import MarkitdownExtractor

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

            extraccion = await _extraer_datos_factura(markdown_text, db)
            if extraccion:
                fd = FacturaDatos(
                    factura_id=factura.id,
                    **extraccion,
                )
                db.add(fd)

            facturas_creadas += 1

    llm_router = None
    try:
        from app.services import llm_router as llm_mod
        llm_router = llm_mod
    except ImportError:
        pass

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


async def _extraer_datos_factura(markdown_text: str, db) -> dict | None:
    try:
        from app.services import llm_router as llm_mod
        extracted = await llm_mod.extract_invoice_data(markdown_text)
        if extracted and extracted.get("numero_factura"):
            return extracted
    except ImportError:
        pass
    except Exception:
        logger.warning("Extracción LLM falló para factura", exc_info=True)
    return None
