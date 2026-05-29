# Tasks: perfiles-ia

## Phase 1: Backend Config

- [x] 1.1 Add `IA_PROFILES` dict in `app/config.py` with 3 stacks: `fast`, `optimized`, `slow`
- [x] 1.2 Simplify `GET /api/config` to return `ia_profile` + resolved models from profile
- [x] 1.3 Simplify `PUT /api/config` to save only `ia_profile` field
- [x] 1.4 Remove `GET /api/config/models` endpoint and `_model_cache`

## Phase 2: Backend Services

- [x] 2.1 Add `LLMError` class + `_parse_openrouter_error` in `app/services/llm_router.py`
- [x] 2.2 Update `_get_model_for_task` to resolve from `IA_PROFILES[profile]`; collapse `_get_provider_config` to OpenRouter-only
- [x] 2.3 Catch `LLMError` in `app/routers/upload.py`, re-raise as `HTTPException` with typed status code
- [x] 2.4 Catch `LLMError` in `app/routers/process.py` (extraction + conciliación)
- [x] 2.5 Catch `LLMError` in `app/routers/reports.py` (email generation)

## Phase 3: Frontend

- [x] 3.1 Replace API keys + 4 model selects with 3 profile cards + hidden `cfg-ia-profile` in `app/templates/config.html`
- [x] 3.2 Add error modal markup (`.modal-overlay > .modal-content > .modal-suggestion + .modal-btn`) in `app/templates/base.html`
- [x] 3.3 Add `selectProfile`/`loadProfile`, `showErrorModal`/`closeErrorModal` in `app/static/js/main.js`; remove `loadAvailableModels`/`populateModelSelect`/`renderModelOptions`
- [x] 3.4 Add `.profile-card` (selected state + hover) and `#error-modal` (overlay + animation) styles in `app/static/css/styles.css`

## Phase 4: Verification

- [ ] 4.1 Verify profile saves and persists on reload (REQ-PROFILE-001)
- [ ] 4.2 Verify all 4 task types resolve models from active profile (REQ-PROFILE-002)
- [ ] 4.3 Verify modal appears for each error type (REQ-ERROR-001 to 005)
- [ ] 4.4 Verify no API key inputs or model selects in UI (REQ-PROFILE-003, REQ-PROFILE-004)
