# Config Specification

## Purpose

Define how the user configures the AI provider for invoice processing through pre-defined profiles, and how the system handles errors from OpenRouter.

## Requirements

### Requirement: Profile Selection (REQ-PROFILE-001)

The system MUST offer 3 pre-defined profiles (Rápido, Optimizado, Lento) displayed as selectable cards in the AI configuration section.

The selected profile MUST be persisted to the database when saved and restored on page reload.

#### Scenario: User selects and saves a profile

- GIVEN the user is on the Configuración page
- WHEN the user clicks the "Rápido" card and clicks "Guardar"
- THEN `ia_profile` MUST be saved as `"rapido"` in the database
- AND a success notification MUST be displayed

#### Scenario: Profile persists on reload

- GIVEN `ia_profile` is `"lento"` in the database
- WHEN the user reloads the Configuración page
- THEN the "Lento" card MUST appear selected

### Requirement: Model Resolution (REQ-PROFILE-002)

Each LLM task (extraction, vision, conciliation, email) MUST use the model mapped to the active profile in `IA_PROFILES` from `app/config.py`.

#### Scenario: Active profile resolves all 4 models

- GIVEN the active profile is `"rapido"`
- WHEN any task triggers an LLM call
- THEN the model used MUST match `IA_PROFILES["rapido"][task_type]`

#### Scenario: Invalid profile fallback

- GIVEN `ia_profile` is set to a non-existent key
- WHEN the system resolves models
- THEN the system MUST default to `"optimizado"`

### Requirement: No API Keys in UI (REQ-PROFILE-003)

The UI MUST NOT display any API key inputs in the configuration section. The OpenRouter API key MUST be read exclusively from the `OPENROUTER_API_KEY` environment variable in `.env`.

#### Scenario: No key inputs visible

- GIVEN the user opens the Configuración page
- WHEN inspecting the form
- THEN no `<input>` for API keys SHALL be present

### Requirement: No Dynamic Model Loading (REQ-PROFILE-004)

The frontend MUST NOT call `GET /api/config/models`. The UI MUST NOT render model selects or search/filter controls for available models.

#### Scenario: No model select rendered

- GIVEN the user opens the Configuración page
- WHEN the page loads
- THEN no dropdown or searchable model list SHALL be displayed

### Requirement: Insufficient Credits Error (REQ-ERROR-001)

When OpenRouter responds with `"Insufficient credits"`, the endpoint MUST return HTTP 402. The frontend MUST display a modal with: "No hay saldo disponible en OpenRouter. Por favor, recargá tu cuenta para continuar." The modal MUST have an "Aceptar" button that closes it.

#### Scenario: OpenRouter returns insufficient credits

- GIVEN the user uploads a file for processing
- WHEN OpenRouter responds with 402 insufficient credits
- THEN the endpoint MUST return HTTP 402
- AND the frontend MUST display the credit error modal

### Requirement: Rate Limit Error (REQ-ERROR-002)

When OpenRouter returns a rate limit response, the endpoint MUST return HTTP 429. The frontend MUST display a modal with a wait message.

#### Scenario: OpenRouter rate limits the request

- GIVEN the user sends multiple requests rapidly
- WHEN OpenRouter responds with a rate limit error
- THEN the endpoint MUST return HTTP 429
- AND the frontend MUST display the rate limit modal

### Requirement: Model Unavailable Error (REQ-ERROR-003)

When OpenRouter indicates the model is unavailable, the endpoint MUST return HTTP 503. The frontend MUST display a modal suggesting the user try another profile.

#### Scenario: Model not available on OpenRouter

- GIVEN a profile uses a deprecated or unavailable model
- WHEN OpenRouter responds with a model-not-found error
- THEN the endpoint MUST return HTTP 503
- AND the frontend MUST display a modal suggesting another profile

### Requirement: Network Error (REQ-ERROR-004)

When a connection error occurs with OpenRouter, the endpoint MUST return HTTP 502. The frontend MUST display a modal asking the user to verify their internet connection.

#### Scenario: Connection to OpenRouter fails

- GIVEN the network is down or OpenRouter is unreachable
- WHEN the system attempts an LLM call
- THEN the endpoint MUST return HTTP 502
- AND the frontend MUST display a connection error modal

### Requirement: Unknown Error (REQ-ERROR-005)

When OpenRouter returns an unrecognized error, the endpoint MUST return HTTP 502. The frontend MUST display a modal with a generic error message.

#### Scenario: OpenRouter returns unexpected error

- GIVEN OpenRouter returns an unexpected error code
- WHEN the system processes the LLM response
- THEN the endpoint MUST return HTTP 502
- AND the frontend MUST display a generic error modal

### Requirement: No Automatic Fallback (REQ-ERROR-006)

If a profile fails with an error, the system MUST NOT automatically switch to another profile. The user MUST manually change the profile in Configuración.

#### Scenario: Profile error does not trigger fallback

- GIVEN the active profile is "rapido" and it fails
- WHEN the error is handled
- THEN `ia_profile` MUST remain `"rapido"`
- AND no automatic switch to another profile SHALL occur

### Requirement: Existing User Migration (REQ-MIGRATE-001)

If `ia_profile` is not set in the database, the system MUST default to `"optimizado"`. Legacy columns (`model_extract`, `model_vision`, etc.) MUST remain in the database but MUST NOT be used for model resolution.

#### Scenario: New user without profile

- GIVEN a user has no `ia_profile` in the database
- WHEN the system checks the active profile
- THEN the effective profile MUST be `"optimizado"`

#### Scenario: Legacy columns ignored

- GIVEN a user has legacy `model_extract` and `model_vision` values in the database
- WHEN the system resolves models for a task
- THEN the legacy columns SHALL be ignored
- AND the model from the active profile SHALL be used
