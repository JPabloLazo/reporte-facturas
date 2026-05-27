import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models import Resumen, Transaccion, Conciliacion, TarjetaUsuario
from app.services.email_generator import EmailGenerator
from app.services.email_sender import EmailSender
from app.services.excel_generator import ExcelGenerator
from app.services.pdf_generator import PDFGenerator
from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)

router = APIRouter()

llm_router = LLMRouter(settings)


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


@router.post("/{resumen_id}/email")
async def send_emails(
    resumen_id: int,
    db: AsyncSession = Depends(get_db),
):
    resumen = await db.get(Resumen, resumen_id)
    if not resumen:
        raise HTTPException(404, "Resumen no encontrado")

    if not settings.smtp_host or not settings.smtp_user:
        raise HTTPException(400, "SMTP no configurado")

    result = await db.execute(
        select(Conciliacion, Transaccion)
        .join(Transaccion)
        .where(Conciliacion.estado == "UNMATCHED")
        .where(Transaccion.resumen_id == resumen_id)
    )
    conciliaciones = list(result.all())

    transacciones_unmatched = [
        {
            "fecha": str(t.fecha),
            "descripcion": t.descripcion,
            "monto": t.monto,
            "numero_tarjeta": t.numero_tarjeta or "",
            "moneda": t.moneda,
        }
        for c, t in conciliaciones
    ]

    if not transacciones_unmatched:
        return {"status": "ok", "message": "No hay transacciones sin factura"}

    resumen_info = {"periodo": resumen.periodo, "tipo": resumen.tipo}
    excel_bytes = ExcelGenerator.generate_unmatched_excel(
        resumen_info, transacciones_unmatched
    )

    asunto, cuerpo = EmailGenerator.generate_email_content(
        transacciones_unmatched, resumen.tipo, resumen.periodo,
        "responsable", llm_router
    )

    enviados = []

    if settings.email_responsable:
        ok = EmailSender.send_email_with_attachment(
            to_email=settings.email_responsable,
            subject=asunto,
            body_html=cuerpo,
            attachment_bytes=excel_bytes,
            settings=settings,
        )
        enviados.append({"to": settings.email_responsable, "status": "ok" if ok else "error"})

    if resumen.tipo == "VISA":
        por_tarjeta = defaultdict(list)
        for t in transacciones_unmatched:
            if t["numero_tarjeta"]:
                por_tarjeta[t["numero_tarjeta"]].append(t)

        for num_tarjeta, trans in por_tarjeta.items():
            result = await db.execute(
                select(TarjetaUsuario).where(TarjetaUsuario.numero_tarjeta == num_tarjeta)
            )
            usuario = result.scalar_one_or_none()
            if usuario and usuario.email_usuario:
                asunto_u, cuerpo_u = EmailGenerator.generate_email_content(
                    trans, resumen.tipo, resumen.periodo,
                    usuario.nombre_usuario, llm_router
                )
                ok = EmailSender.send_email_with_attachment(
                    to_email=usuario.email_usuario,
                    subject=asunto_u,
                    body_html=cuerpo_u,
                    attachment_bytes=excel_bytes,
                    settings=settings,
                )
                enviados.append({"to": usuario.email_usuario, "status": "ok" if ok else "error"})

    return {
        "status": "ok",
        "message": f"Emails enviados: {len(enviados)}",
        "enviados": enviados,
    }
