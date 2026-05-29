Stack: FastAPI async + SQLite (aiosqlite) + Jinja2/vanilla JS.
Router: /api/upload, /api/process, /api/reports, /api/drive, /api/config.
Models: Resumen, Transaccion, Conciliacion, Factura, FacturaDatos, DriveSession.
LLM: OpenRouter via LLMRouter. SDD: openspec/. Env: OPENROUTER_API_KEY, GOOGLE_CLIENT_ID/SECRET.
Tests: none. SDK: sdd-orchestrator agent.