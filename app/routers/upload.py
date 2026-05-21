import base64
import io
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
    TipoResumen,
    TransaccionExtraida,
)
from app.services.llm_router import LLMRouter

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

    try:
        tipo = ResumenParser.detectar_tipo(save_path)
    except ValueError:
        os.remove(save_path)
        raise HTTPException(400, "Tipo de resumen no reconocido")

    modo = "vision"
    transacciones_extraidas: list[TransaccionExtraida] = []

    llm_instance = None
    if settings.openrouter_api_key or settings.anthropic_api_key or settings.openai_api_key:
        llm_instance = LLMRouter(settings)

    images_pil = convert_from_path(save_path, dpi=200)
    images_b64 = []
    for img in images_pil:
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85)
        images_b64.append(base64.b64encode(buf.getvalue()).decode('utf-8'))
    transacciones_extraidas = ResumenParser.parsear_fallback_vision(images_b64, llm_instance)

    if not transacciones_extraidas:
        os.remove(save_path)
        has_llm = bool(settings.openrouter_api_key or settings.anthropic_api_key or settings.openai_api_key)
        if not has_llm:
            raise HTTPException(400, "No se pudieron extraer transacciones. El PDF podría ser una imagen (foto de WhatsApp). Configurá una API key de IA en Configuración > Proveedores de IA para activar el procesamiento por imagen.")
        raise HTTPException(400, "No se pudieron extraer transacciones del PDF. Verificá que el formato del resumen sea compatible (AMEX o VISA).")

    periodo = _infer_periodo(transacciones_extraidas)
    resumen = Resumen(
        tipo=tipo.value,
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
            tipo=tipo.value,
        )
        db.add(trans)
        if t.numero_tarjeta and t.numero_tarjeta not in known_cards:
            unmatched.append(t.numero_tarjeta)

    await db.commit()
    await db.refresh(resumen)

    return {
        "id": resumen.id,
        "tipo": tipo.value,
        "periodo": periodo,
        "archivo": file.filename,
        "modo": modo,
        "transacciones": [
            {
                "fecha": t.fecha,
                "descripcion": t.descripcion,
                "monto": t.monto,
                "numero_tarjeta": t.numero_tarjeta,
                "moneda": t.moneda,
            }
            for t in transacciones_extraidas
        ],
        "warnings": (
            [{"codigo": "TARJETAS_SIN_MAPEO", "tarjetas": list(set(unmatched))}]
            if unmatched
            else []
        ),
    }
