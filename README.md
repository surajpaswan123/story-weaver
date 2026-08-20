# Story Weaver

Story Weaver is a FastAPI web application for long-form, multi-provider AI story generation with account-scoped stories, reference files, undo, audio input, and browser-direct local-model support.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

The server binds to `127.0.0.1:8000` by default. `Start_Story_Weaver.bat` starts the app from the directory containing the script and, when present, starts the optional Gemini-Nokey proxy on `127.0.0.1:8080`.

For an intentionally unauthenticated local-only installation, set `ALLOW_LOCAL_SUPER_ADMIN=true`. Unverified JWT decoding is allowed only on an unhosted local server without Firebase Admin; hosted runtimes always fail closed.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## Hosted deployment

Configure Firebase Admin credentials before exposing the application publicly. Provider API keys are stored per signed-in account through Settings; guests are read-only. Server-side custom OpenAI-compatible endpoints must use HTTPS and resolve only to public IP addresses. Leave `TRUST_PROXY_HEADERS=false` unless the app is behind a trusted proxy that overwrites the forwarded-client headers.
