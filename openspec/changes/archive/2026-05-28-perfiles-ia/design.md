# Design: perfiles-ia

## Technical Approach

Replace granular LLM config (4 models + 3 API keys + provider selector) with 3 predefined profiles hardcoded in `config.py`. Collapse `_get_provider_config` to resolve models from `IA_PROFILES[profile]` via OpenRouter only. Add typed error handling (`LLMError`) with frontend modal. Remove `GET /api/config/models` and all model-listing UI.

## Architecture Decisions

### Decision 1: OpenRouter as sole provider

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Keep Anthropic/OpenAI/OpenRouter multi-provider | User chooses API key + model, flexible but complex | Rejected |
| OpenRouter only | Single API key, profile dictates model; loses direct Anthropic/OpenAI | **Chosen** |

Simplify wins over flexibility. Profiles are opinionated stacks — if a model moves, update `IA_PROFILES` in `config.py`.

### Decision 2: Hardcoded profiles vs DB-stored

| Option | Tradeoff | Decision |
|--------|----------|----------|
| DB table for profiles | Editable from UI, requires migration + CRUD | Rejected |
| Dict in `config.py` | Zero-dependency, code change = profile change | **Chosen** |

Per proposal scope — no dynamic model loading. Profiles are deployment config.

### Decision 3: LLMError propagation

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Wrap in routers only | Services still raise ValueError elsewhere | Rejected |
| LLMError in `llm_router.py`, caught in 3 routers | Typed errors everywhere, clean HTTP codes | **Chosen** |

`LLMError` carries `type` enum → status map → user-facing suggestion.

### Decision 4: Frontend error modal vs toast

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Toast only | Simple but easy to miss for critical errors | Rejected |
| Modal with typed suggestion | Obvious, specific guidance per error type | **Chosen** |

## Data Flow

```
Config page: profile card click → set hidden input → save → PUT /api/config {ia_profile}
                                                              → DB key "ia_profile"

LLM call: request → router → llm_router.chat()
                                ↓
                          _get_model_for_task(task_type)
                                ↓
                          IA_PROFILES[profile][task_type]
                                ↓
                          OpenRouter API → LLMError or response
                                ↓
                          Router catches LLMError → HTTPException(status, detail{suggestion})
                                ↓
                          Frontend fetch catch → showErrorModal()
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/config.py` | Modify | Add `IA_PROFILES` dict with 3 stacks; remove `default_llm_provider`, `model_*` fields (keep for backward compat) |
| `app/routers/config.py` | Modify | `GET /api/config` returns `ia_profile` + resolved models; `PUT /api/config` saves only `ia_profile`; delete `GET /api/config/models` and `_model_cache` |
| `app/services/llm_router.py` | Modify | Add `LLMError(Exception)`, `_parse_openrouter_error`, `_get_model_for_task`; collapse `_get_provider_config` to OpenRouter-only; raise `LLMError` instead of `ValueError` |
| `app/routers/upload.py` | Modify | Import `LLMError`, catch around LLM calls, re-raise as `HTTPException` |
| `app/routers/process.py` | Modify | Import `LLMError`, catch around LLM calls (extraction + conciliacion) |
| `app/routers/reports.py` | Modify | Import `LLMError`, catch around email generation |
| `app/templates/config.html` | Modify | Replace API keys + 4 model selects with 3 profile cards + hidden `cfg-ia-profile` input |
| `app/templates/base.html` | Modify | Add error modal markup at end of body |
| `app/static/js/main.js` | Modify | Add `selectProfile`/`loadProfile`, `showErrorModal`/`closeErrorModal`; modify `initConfig`/`loadConfig`; remove `loadAvailableModels`/`populateModelSelect`/`renderModelOptions`; update fetch catch blocks |
| `app/static/css/styles.css` | Modify | Add `.profile-card` and `#error-modal` animations |

## Interfaces / Contracts

### GET /api/config response (new shape)

```python
{
    "ia_profile": "optimized",          # "fast" | "optimized" | "slow"
    "ia_models": {
        "extraction": "deepseek/deepseek-chat-v3-0324",
        "vision": "openai/gpt-4o-mini",
        "reconciliation": "deepseek/deepseek-chat",
        "email": "openai/gpt-4o-mini"
    },
    "smtp_host": "...",                  # unchanged
    "smtp_port": 587,
    "smtp_user": "...",
    "smtp_pass": "...",
    "responsable_email": "...",
    "cards": [...]
}
```

Removed: `llm_provider`, `anthropic_key`, `openai_key`, `openrouter_key`, `model_extract`, `model_fallback`, `model_cheap`, `model_email`.

### PUT /api/config request (new shape)

```python
{
    "ia_profile": "fast",               # new
    "smtp_host": "...",                  # unchanged
    "smtp_port": 587,
    "smtp_user": "...",
    "smtp_pass": "...",
    "responsable_email": "..."
}
```

### LLMError

```python
class LLMError(Exception):
    def __init__(self, type: str, message: str, provider: str = "openrouter"):
        # type: insufficient_credits | rate_limit | model_unavailable | network_error | unknown
```

### Error response shape (from routers)

```python
{
    "error_type": "insufficient_credits",
    "message": "Insufficient credits...",
    "suggestion": "No hay saldo disponible en OpenRouter..."
}
```

### Status code map

| LLMError type | HTTP status |
|---------------|-------------|
| `insufficient_credits` | 402 |
| `rate_limit` | 429 |
| `model_unavailable` | 503 |
| `network_error` | 502 |
| `unknown` | 502 |

## Testing Strategy

No test framework present. Verification via manual testing per success criteria in proposal.

## Migration / Rollout

No migration required. Existing DB settings (`model_extract`, `model_fallback`, etc.) remain in DB but become inert — new code reads `ia_profile` only. Rollback: `git checkout` the 10 affected files.

## Open Questions

None.
