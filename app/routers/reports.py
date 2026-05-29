import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, func, case, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models import Resumen, Transaccion, Conciliacion, TarjetaUsuario, Factura, FacturaDatos
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


@router.get("/historial")
async def list_historial(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Devuelve lista paginada de resumenes con conteos agregados."""
    count_result = await db.execute(select(func.count(Resumen.id)))
    total = count_result.scalar()

    stmt = (
        select(
            Resumen.id,
            Resumen.periodo,
            Resumen.tipo,
            Resumen.archivo_nombre,
            Resumen.fecha_procesado,
            func.count(Transaccion.id).label("total_transacciones"),
            func.sum(case((Conciliacion.estado == "MATCHED", 1), else_=0)).label("matched_count"),
            func.sum(case((Conciliacion.estado == "UNMATCHED", 1), else_=0)).label("unmatched_count"),
        )
        .outerjoin(Transaccion, Transaccion.resumen_id == Resumen.id)
        .outerjoin(Conciliacion, Conciliacion.transaccion_id == Transaccion.id)
        .group_by(Resumen.id)
        .order_by(Resumen.fecha_procesado.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    items = []
    for row in rows:
        items.append({
            "id": row.id,
            "periodo": row.periodo,
            "tipo": row.tipo,
            "archivo_nombre": row.archivo_nombre,
            "fecha_procesado": row.fecha_procesado.isoformat() if row.fecha_procesado else None,
            "total_transacciones": row.total_transacciones or 0,
            "matched_count": row.matched_count or 0,
            "unmatched_count": row.unmatched_count or 0,
        })

    return {"items": items, "total": total}


@router.delete("/historial/{resumen_id}")
async def delete_historial(
    resumen_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Elimina un resumen y todos sus registros dependientes."""
    result = await db.execute(select(Resumen).where(Resumen.id == resumen_id))
    resumen = result.scalar_one_or_none()
    if not resumen:
        raise HTTPException(404, "Resumen no encontrado")

    # Obtener transacciones del resumen
    trans_result = await db.execute(select(Transaccion.id).where(Transaccion.resumen_id == resumen_id))
    trans_ids = [r[0] for r in trans_result.all()]

    if trans_ids:
        # Obtener conciliaciones y facturas asociadas
        conc_result = await db.execute(
            select(Conciliacion.factura_id).where(Conciliacion.transaccion_id.in_(trans_ids))
        )
        factura_ids = [r[0] for r in conc_result.all() if r[0] is not None]

        # Eliminar conciliaciones
        await db.execute(delete(Conciliacion).where(Conciliacion.transaccion_id.in_(trans_ids)))

        # Eliminar facturas que no tengan otras conciliaciones
        if factura_ids:
            unique_factura_ids = list(set(factura_ids))
            other_conc = await db.execute(
                select(Conciliacion.factura_id)
                .where(Conciliacion.factura_id.in_(unique_factura_ids))
                .where(Conciliacion.transaccion_id.notin_(trans_ids))
            )
            other_factura_ids = {r[0] for r in other_conc.all() if r[0] is not None}
            deletable = [fid for fid in unique_factura_ids if fid not in other_factura_ids]

            if deletable:
                await db.execute(delete(FacturaDatos).where(FacturaDatos.factura_id.in_(deletable)))
                await db.execute(delete(Factura).where(Factura.id.in_(deletable)))

        # Eliminar transacciones
        await db.execute(delete(Transaccion).where(Transaccion.id.in_(trans_ids)))

    # Eliminar resumen
    await db.execute(delete(Resumen).where(Resumen.id == resumen_id))
    await db.commit()

    return {"success": True}


@router.get("/{resumen_id}")
async def get_resumen(resumen_id: int, db: AsyncSession = Depends(get_db)):
    # Get resumen
    result = await db.execute(select(Resumen).where(Resumen.id == resumen_id))
    resumen = result.scalar_one_or_none()
    if not resumen:
        raise HTTPException(404, "Resumen no encontrado")

    # Query transacciones with conciliaciones LEFT JOINed
    stmt = (
        select(
            Transaccion,
            Conciliacion.estado,
            Conciliacion.confianza,
            Conciliacion.metodo,
            Factura.id.label("factura_id"),
            Factura.drive_file_name,
            FacturaDatos.monto_total,
            FacturaDatos.emisor,
            FacturaDatos.cuit_emisor,
            FacturaDatos.tipo_factura,
            FacturaDatos.numero_factura,
            FacturaDatos.fecha,
        )
        .outerjoin(Conciliacion, Conciliacion.transaccion_id == Transaccion.id)
        .outerjoin(Factura, Factura.id == Conciliacion.factura_id)
        .outerjoin(FacturaDatos, FacturaDatos.factura_id == Factura.id)
        .where(Transaccion.resumen_id == resumen_id)
        .order_by(Transaccion.fecha)
    )
    rows = (await db.execute(stmt)).all()

    transacciones = []
    for row in rows:
        t = row.Transaccion
        tx = {
            "fecha": str(t.fecha),
            "descripcion": t.descripcion,
            "monto": t.monto,
            "numero_tarjeta": t.numero_tarjeta,
            "moneda": t.moneda,
            "tipo_tarjeta": t.tipo,
            "cantidad_cuotas": t.cantidad_cuotas,
            "cuotas_faltantes": t.cuotas_faltantes,
            "cuota_numero": t.cuota_numero,
            "estado": row.estado,
            "confianza": row.confianza,
            "metodo": row.metodo,
        }
        if row.estado == "MATCHED" and row.factura_id:
            tx["factura"] = {
                "drive_file_name": row.drive_file_name,
                "monto_total": row.monto_total,
                "emisor": row.emisor,
                "cuit_emisor": row.cuit_emisor,
                "tipo_factura": row.tipo_factura,
                "numero_factura": row.numero_factura,
                "fecha": row.fecha,
            }
        else:
            tx["factura"] = None

        transacciones.append(tx)

    return {
        "id": resumen.id,
        "tipo": resumen.tipo,
        "periodo": resumen.periodo,
        "archivo": resumen.archivo_nombre,
        "transacciones": transacciones,
    }
