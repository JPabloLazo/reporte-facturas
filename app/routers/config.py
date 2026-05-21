import asyncio
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.dependencies import get_db
from app.models import Setting, TarjetaUsuario
from app.config import settings

router = APIRouter()


@router.get("")
async def get_config(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Setting))
    db_settings = {row.key: row.value for row in result.scalars().all()}

    result = await db.execute(select(TarjetaUsuario))
    cards = result.scalars().all()

    return {
        "llm_provider": db_settings.get("llm_provider", settings.default_llm_provider),
        "anthropic_key": db_settings.get("anthropic_key", ""),
        "openai_key": db_settings.get("openai_key", ""),
        "openrouter_key": db_settings.get("openrouter_key", ""),
        "model_extract": db_settings.get("model_extract", settings.model_extraction),
        "model_fallback": db_settings.get("model_fallback", settings.model_vision),
        "model_cheap": db_settings.get("model_cheap", settings.model_reconciliation),
        "model_email": db_settings.get("model_email", settings.model_email),
        "smtp_host": db_settings.get("smtp_host", settings.smtp_host),
        "smtp_port": int(db_settings.get("smtp_port", settings.smtp_port)),
        "smtp_user": db_settings.get("smtp_user", ""),
        "smtp_pass": db_settings.get("smtp_pass", ""),
        "responsable_email": db_settings.get("responsable_email", settings.email_responsable),
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


_model_cache = {"data": None, "expires": None}


@router.get("/models")
async def list_models(db: AsyncSession = Depends(get_db)):
    """Fetch available models from configured providers (OpenRouter, OpenAI, Anthropic).
    Caches for 30 minutes."""
    global _model_cache
    
    # Check cache
    if _model_cache["data"] and _model_cache["expires"] and datetime.now() < _model_cache["expires"]:
        return {"models": _model_cache["data"]}
    
    # Read API keys from DB
    result = await db.execute(select(Setting).where(Setting.key.in_(["openrouter_key", "openai_key", "anthropic_key"])))
    db_settings = {row.key: row.value for row in result.scalars().all()}
    
    # Also check env fallback
    or_key = db_settings.get("openrouter_key") or settings.openrouter_api_key
    oa_key = db_settings.get("openai_key") or settings.openai_api_key
    an_key = db_settings.get("anthropic_key") or settings.anthropic_api_key
    
    all_models = []
    
    # 1. OpenRouter (public endpoint, no key needed to list)
    try:
        headers = {"Content-Type": "application/json"}
        if or_key:
            headers["Authorization"] = f"Bearer {or_key}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get("https://openrouter.ai/api/v1/models", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("data", []):
                    all_models.append({
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "provider": "openrouter",
                    })
    except Exception:
        pass
    
    # 2. OpenAI
    if oa_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {oa_key}"}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("data", []):
                        all_models.append({
                            "id": m["id"],
                            "name": m["id"],
                            "provider": "openai",
                        })
        except Exception:
            pass
    
    # 3. Anthropic
    if an_key:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://api.anthropic.com/v1/models",
                    headers={
                        "x-api-key": an_key,
                        "anthropic-version": "2023-06-01"
                    }
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for m in data.get("data", []):
                        all_models.append({
                            "id": m.get("id") or m.get("name", ""),
                            "name": m.get("display_name") or m.get("name") or m.get("id", ""),
                            "provider": "anthropic",
                        })
        except Exception:
            pass
    
    # Deduplicate by id
    seen = set()
    unique_models = []
    for m in all_models:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique_models.append(m)
    
    # Sort by provider, then name
    unique_models.sort(key=lambda x: (x["provider"], x["name"]))
    
    # Cache
    _model_cache["data"] = unique_models
    _model_cache["expires"] = datetime.now() + timedelta(minutes=30)
    
    return {"models": unique_models}


@router.put("")
async def save_config(data: dict, db: AsyncSession = Depends(get_db)):
    mapping = {
        "llm_provider": "llm_provider",
        "anthropic_key": "anthropic_key",
        "openai_key": "openai_key",
        "openrouter_key": "openrouter_key",
        "model_extract": "model_extract",
        "model_fallback": "model_fallback",
        "model_cheap": "model_cheap",
        "model_email": "model_email",
        "smtp_host": "smtp_host",
        "smtp_port": "smtp_port",
        "smtp_user": "smtp_user",
        "smtp_pass": "smtp_pass",
        "responsable_email": "responsable_email",
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


