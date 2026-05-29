import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models import Resumen, Transaccion, Conciliacion, TarjetaUsuario
from app.services.email_generator import EmailGenerator
from app.services.excel_generator import ExcelGenerator
from app.services.pdf_generator import PDFGenerator
from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{resumen_id}/excel")
async def download_excel(
    resumen_id: int,
    filter: str = Query("unmatched", regex="^(unmatched|matched|all)$"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Resumen).where(Resumen.id == resumen_id))
    resumen = result.scalar_one_or_none()
    if not resumen:
        raise HTTPException(404, "Resumen no encontrado")

    trans_result = await db.execute(
        select(Transaccion).where(Transaccion.resumen_id == resumen_id)
    )
    transacciones = trans_result.scalars().all()

    conc_result = await db.execute(
        select(Conciliacion).where(
            Conciliacion.transaccion_id.in_([t.id for t in transacciones])
        )
    )
    conciliaciones = conc_result.scalars().all()

    if filter == "matched":
        filtered_ids = {c.transaccion_id for c in conciliaciones if c.estado == "MATCHED"}
    elif filter == "unmatched":
        filtered_ids = {c.transaccion_id for c in conciliaciones if c.estado == "UNMATCHED"}
    else:
        filtered_ids = {c.transaccion_id for c in conciliaciones}

    transacciones_filtered = [
        {
            "fecha": str(t.fecha),
            "descripcion": t.descripcion,
            "monto": t.monto,
            "numero_tarjeta": t.numero_tarjeta or "",
            "moneda": t.moneda,
        }
        for t in transacciones
        if t.id in filtered_ids
    ]

    resumen_info = {
        "periodo": resumen.periodo,
        "tipo": resumen.tipo,
    }

    excel_bytes = ExcelGenerator.generate_unmatched_excel(
        resumen_info=resumen_info,
        transacciones=transacciones_filtered,
    )

    tipo_filter = {"matched": "con_factura", "unmatched": "sin_factura", "all": "todas"}
    suffix = tipo_filter.get(filter, "sin_factura")
    filename = f"pagos_{suffix}_{resumen.periodo}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.get("/{resumen_id}/transactions/excel")
async def download_transactions_excel(
    resumen_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Resumen).where(Resumen.id == resumen_id))
    resumen = result.scalar_one_or_none()
    if not resumen:
        raise HTTPException(404, "Resumen no encontrado")

    trans_result = await db.execute(
        select(Transaccion).where(Transaccion.resumen_id == resumen_id)
    )
    transacciones = trans_result.scalars().all()

    transacciones_data = [
        {
            "fecha": str(t.fecha),
            "descripcion": t.descripcion,
            "monto": t.monto,
            "numero_tarjeta": t.numero_tarjeta or "",
            "moneda": t.moneda,
            "cantidad_cuotas": t.cantidad_cuotas,
            "cuota_numero": t.cuota_numero,
        }
        for t in transacciones
    ]

    resumen_info = {
        "periodo": resumen.periodo,
        "tipo": resumen.tipo,
        "archivo": resumen.archivo_nombre,
    }

    excel_bytes = ExcelGenerator.generate_transactions_excel(
        resumen_info=resumen_info,
        transacciones=transacciones_data,
    )

    filename = f"transacciones_{resumen.periodo}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.get("/{resumen_id}/transactions/pdf")
async def download_transactions_pdf(
    resumen_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Resumen).where(Resumen.id == resumen_id))
    resumen = result.scalar_one_or_none()
    if not resumen:
        raise HTTPException(404, "Resumen no encontrado")

    trans_result = await db.execute(
        select(Transaccion).where(Transaccion.resumen_id == resumen_id)
    )
    transacciones = trans_result.scalars().all()

    transacciones_data = [
        {
            "fecha": str(t.fecha),
            "descripcion": t.descripcion,
            "monto": t.monto,
            "numero_tarjeta": t.numero_tarjeta or "",
            "moneda": t.moneda,
            "cantidad_cuotas": t.cantidad_cuotas,
            "cuota_numero": t.cuota_numero,
        }
        for t in transacciones
    ]

    resumen_info = {
        "periodo": resumen.periodo,
        "tipo": resumen.tipo,
        "archivo": resumen.archivo_nombre,
    }

    pdf_bytes = PDFGenerator.generate_transactions_pdf(
        resumen_info=resumen_info,
        transacciones=transacciones_data,
    )

    filename = f"transacciones_{resumen.periodo}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


@router.post("/{resumen_id}/email/preview")
async def email_preview(
    resumen_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Genera borradores de email via LLM agrupados por titular de tarjeta."""
    resumen = await db.get(Resumen, resumen_id)
    if not resumen:
        raise HTTPException(404, "Resumen no encontrado")

    result = await db.execute(
        select(Conciliacion, Transaccion)
        .join(Transaccion)
        .where(Conciliacion.estado == "UNMATCHED")
        .where(Transaccion.resumen_id == resumen_id)
    )
    conciliaciones = list(result.all())

    if not conciliaciones:
        return {"status": "ok", "drafts": [], "message": "No hay transacciones sin factura"}

    transacciones = [
        {
            "id": t.id,
            "fecha": str(t.fecha),
            "descripcion": t.descripcion,
            "monto": t.monto,
            "numero_tarjeta": t.numero_tarjeta or "",
            "moneda": t.moneda,
        }
        for c, t in conciliaciones
    ]

    result = await db.execute(select(TarjetaUsuario))
    tarjetas = [
        {
            "numero_tarjeta": t.numero_tarjeta,
            "nombre_usuario": t.nombre_usuario,
            "email_usuario": t.email_usuario,
        }
        for t in result.scalars().all()
    ]

    llm_router = None
    if settings.openrouter_api_key:
        llm_router = LLMRouter(settings)

    drafts = EmailGenerator.generate_emails(
        transacciones_unmatched=transacciones,
        tipo_resumen=resumen.tipo,
        periodo=resumen.periodo,
        tarjetas=tarjetas,
        llm_router=llm_router,
    )

    return {"status": "ok", "drafts": drafts, "message": f"{len(drafts)} borradores generados"}
