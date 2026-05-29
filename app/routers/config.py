from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_db
from app.models import Setting, TarjetaUsuario
from app.config import settings, IA_PROFILES, DEFAULT_IA_PROFILE

router = APIRouter()


@router.get("")
async def get_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    db_settings = {row.key: row.value for row in result.scalars().all()}

    result = await db.execute(select(TarjetaUsuario))
    cards = result.scalars().all()

    # Leer ia_profile de DB
    ia_profile = db_settings.get("ia_profile", DEFAULT_IA_PROFILE)
    if ia_profile not in IA_PROFILES:
        ia_profile = DEFAULT_IA_PROFILE

    # Resolver modelos desde el perfil
    ia_models = IA_PROFILES[ia_profile]

    return {
        "ia_profile": ia_profile,
        "ia_models": ia_models,
        "cards": [
            {
                "id": c.id,
                "card_suffix": c.numero_tarjeta,
                "responsable": c.nombre_usuario,
                "email": c.email_usuario,
            }
            for c in cards
        ],
    }


@router.put("")
async def save_config(data: dict, db: AsyncSession = Depends(get_db)):
    mapping = {
        "ia_profile": "ia_profile",
    }

    for json_key, db_key in mapping.items():
        if json_key in data:
            result = await db.execute(select(Setting).where(Setting.key == db_key))
            existing = result.scalar_one_or_none()
            if existing:
                existing.value = str(data[json_key])
            else:
                db.add(Setting(key=db_key, value=str(data[json_key])))

    await db.commit()

    if "ia_profile" in data:
        settings.ia_profile = data["ia_profile"]

    return {"status": "ok"}


@router.get("/cards")
async def get_cards(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TarjetaUsuario))
    cards = result.scalars().all()
    return [
        {
            "id": c.id,
            "card_suffix": c.numero_tarjeta,
            "responsable": c.nombre_usuario,
            "email": c.email_usuario,
        }
        for c in cards
    ]


@router.post("/cards")
async def add_card(data: dict, db: AsyncSession = Depends(get_db)):
    card = TarjetaUsuario(
        numero_tarjeta=data.get("card_suffix", ""),
        nombre_usuario=data.get("responsable", ""),
        email_usuario=data.get("email", ""),
    )
    db.add(card)
    await db.commit()
    await db.refresh(card)
    return {"id": card.id, "status": "ok"}


@router.delete("/cards/{card_id}")
async def delete_card(card_id: int, db: AsyncSession = Depends(get_db)):
    card = await db.get(TarjetaUsuario, card_id)
    if card:
        await db.delete(card)
    await db.commit()

    return {"status": "ok"}


