import asyncio
import base64
import io
import logging
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pdf2image import convert_from_path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models import Resumen, Transaccion, TarjetaUsuario
from app.services.pdf_parser import (
    ResumenParser,
    TransaccionExtraida,
)
from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)
router = APIRouter()


def _infer_periodo(transacciones: list[TransaccionExtraida]) -> str:
    if not transacciones:
        now = datetime.now()
        return f"{now.year}-{now.month:02d}"
    first = transacciones[0].fecha
    parts = first.replace("-", "/").split("/")
    if len(parts) >= 3:
        return f"{parts[2]}-{parts[1].zfill(2)}"
    now = datetime.now()
    return f"{now.year}-{now.month:02d}"


def _parse_fecha(fecha_str: str) -> datetime.date:
    clean = fecha_str.split(" ")[0]
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return datetime.now().date()


@router.post("")
async def upload_resumen(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(400, "Archivo no proporcionado")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Solo se aceptan archivos PDF")

    file_id = str(uuid.uuid4())
    safe_name = file.filename.replace(" ", "_")
    save_path = os.path.join(settings.upload_dir, f"{file_id}_{safe_name}")
    os.makedirs(settings.upload_dir, exist_ok=True)

    content = await file.read()
    if not content:
        raise HTTPException(400, "Archivo vacío")
    with open(save_path, "wb") as f:
        f.write(content)

    # Detect tipo por keywords (fallback rápido, nunca falla)
    tipo_fallback = ResumenParser.detectar_tipo(save_path)

    modo = "vision"
    transacciones_extraidas: list[TransaccionExtraida] = []

    llm_instance = None
    if settings.openrouter_api_key or settings.anthropic_api_key or settings.openai_api_key or settings.opencode_api_key:
        llm_instance = LLMRouter(settings)

    images_pil = await asyncio.to_thread(convert_from_path, save_path, dpi=100)
    if len(images_pil) > 15:
        logger.warning("PDF tiene %d páginas, limitando a 15", len(images_pil))
        images_pil = images_pil[:15]
    images_b64 = []
    for img in images_pil:
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=50)
        images_b64.append(base64.b64encode(buf.getvalue()).decode('utf-8'))

    # Fase 1: Conteo previo de transacciones (página por página en paralelo)
    expected_count = None
    if llm_instance:
        sem_count = asyncio.Semaphore(3)

        async def _count_page(img_b64: str) -> int | None:
            async with sem_count:
                return await asyncio.to_thread(
                    llm_instance.count_transactions, [img_b64], tipo_fallback
                )

        count_results = await asyncio.gather(*[_count_page(img) for img in images_b64])
        valid_counts = [c for c in count_results if c is not None]
        if valid_counts:
            expected_count = sum(valid_counts)

    transacciones_extraidas, parser_warnings = await ResumenParser.procesar_resumen_async(
        images_b64, llm_instance, card_type=tipo_fallback, expected_count=expected_count
    )

    if not transacciones_extraidas:
        os.remove(save_path)
        has_llm = bool(settings.openrouter_api_key or settings.anthropic_api_key or settings.openai_api_key or settings.opencode_api_key)
        if not has_llm:
            raise HTTPException(400, "No se pudieron extraer transacciones. El PDF podría ser una imagen (foto de WhatsApp). Configurá una API key de IA en Configuración > Proveedores de IA para activar el procesamiento por imagen.")
        raise HTTPException(400, "No se pudieron extraer transacciones del PDF. Verificá que el formato del resumen sea compatible (AMEX o VISA).")

    # Usar tipo_tarjeta del LLM como primario, fallback al keyword scan
    tipo_llm = transacciones_extraidas[0].tipo_tarjeta if transacciones_extraidas else "DESCONOCIDO"
    tipo_final = tipo_llm if tipo_llm != "DESCONOCIDO" else tipo_fallback

    periodo = _infer_periodo(transacciones_extraidas)
    resumen = Resumen(
        tipo=tipo_final,
        periodo=periodo,
        archivo_nombre=file.filename,
    )
    db.add(resumen)
    await db.flush()

    known_cards: set[str] = set()
    result = await db.execute(select(TarjetaUsuario.numero_tarjeta))
    for row in result.scalars().all():
        known_cards.add(row)

    unmatched: list[str] = []
    for t in transacciones_extraidas:
        trans = Transaccion(
            resumen_id=resumen.id,
            fecha=_parse_fecha(t.fecha),
            descripcion=t.descripcion,
            monto=t.monto,
            numero_tarjeta=t.numero_tarjeta,
            moneda=t.moneda,
            tipo=t.tipo_tarjeta if t.tipo_tarjeta and t.tipo_tarjeta != "DESCONOCIDO" else tipo_fallback,
            cantidad_cuotas=t.cantidad_cuotas,
            cuotas_faltantes=t.cuotas_faltantes,
            cuota_numero=t.cuota_numero,
        )
        db.add(trans)
        if t.numero_tarjeta and t.numero_tarjeta not in known_cards:
            unmatched.append(t.numero_tarjeta)

    await db.commit()
    await db.refresh(resumen)

    # Determinar modo
    modo_final = "vision"
    if parser_warnings:
        modo_final = "vision+retry"

    # Merge warnings
    all_warnings = list(parser_warnings)
    if unmatched:
        all_warnings.append({"codigo": "TARJETAS_SIN_MAPEO", "tarjetas": list(set(unmatched))})
    if expected_count is None and llm_instance:
        all_warnings.append({"codigo": "CONTEO_FALLIDO", "mensaje": "No se pudo contar transacciones previo a la extracción. El resultado puede estar incompleto."})

    requiere_decision = any(w.get("codigo") == "CONTEO_DIFERENTE_POST_REINTENTO" for w in parser_warnings)

    return {
        "id": resumen.id,
        "tipo": tipo_final,
        "periodo": periodo,
        "archivo": file.filename,
        "modo": modo_final,
        "transacciones": [
            {
                "fecha": t.fecha,
                "descripcion": t.descripcion,
                "monto": t.monto,
                "numero_tarjeta": t.numero_tarjeta,
                "moneda": t.moneda,
                "tipo_tarjeta": t.tipo_tarjeta,
                "cantidad_cuotas": t.cantidad_cuotas,
                "cuotas_faltantes": t.cuotas_faltantes,
                "cuota_numero": t.cuota_numero,
            }
            for t in transacciones_extraidas
        ],
        "warnings": all_warnings,
        "requiere_decision_usuario": requiere_decision,
        "opciones_disponibles": ["reintentar", "continuar"] if requiere_decision else [],
    }
