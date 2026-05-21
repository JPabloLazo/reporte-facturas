---
name: impl-facturas-infra
description: >
  Crea el scaffold del proyecto facturas: requirements.txt, app/main.py,
  app/config.py, app/database.py, app/models.py, app/dependencies.py.
  Trigger: Cuando se necesita crear o regenerar la infraestructura base del backend FastAPI.
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## When to Use

- Primera ejecución del proyecto (no existe nada en `app/`)
- Se necesita regenerar models, config, o database desde cero
- Se agregan nuevos modelos a `app/models.py` o variables de entorno a `app/config.py`

## Critical Patterns

- **Stack**: Python 3.10+, FastAPI, SQLite con SQLAlchemy 2.0, Uvicorn
- **Naming**: `app/` como package Python (debe tener `__init__.py`). Archivos: `main.py`, `config.py`, `database.py`, `models.py`, `dependencies.py`
- **DB**: Usar SQLAlchemy async (`create_async_engine`, `AsyncSession`) con `aiosqlite`
- **Config**: Variables vía `pydantic-settings` (`BaseSettings`). Cargar desde `.env` en desarrollo
- **Models**: Base declarativa con `declarative_base()`. Todos los modelos en un solo archivo `models.py`
- **Dependencies**: Inyección de sesión DB vía `Depends(get_db)` en `dependencies.py`
- **main.py**: Crear `FastAPI` app con lifespan, incluir routers via `include_router`, CORS middleware básico
- **requirements.txt**: Listar `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `aiosqlite`, `pydantic-settings`

## Code Examples

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./facturas.db"
    secret_key: str = "change-me"

    class Config:
        env_file = ".env"

settings = Settings()
```

```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

engine = create_async_engine("sqlite+aiosqlite:///./facturas.db")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with async_session() as session:
        yield session
```

## Commands

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Dependencies

- Ninguna (es el skill raíz del proyecto)

## Resources

- `app/__init__.py`
- `app/main.py`
- `app/config.py`
- `app/database.py`
- `app/models.py`
- `app/dependencies.py`
- `requirements.txt`
