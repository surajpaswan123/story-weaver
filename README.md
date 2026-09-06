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

## Responses API providers

In Settings, use the **OpenAI API Key** section for a custom hosted provider.
The URL accepts either a base URL or a full `/responses` or `/chat/completions`
endpoint. For OpenCode Zen, use `https://opencode.ai/zen/v1`. Story Weaver
chooses the API format for each model on every request: Muse Spark (including
Contributor Free), GPT, and Grok use Responses; Chat Completions models such
as MiMo, DeepSeek, GLM, and MiniMax use Chat Completions. This also applies
when the story, background, and rules models differ. Existing saved full
URLs and format selections still work with this automatic OpenCode routing.
OpenCode's Claude/Qwen and Gemini endpoints require other protocols; the
OpenAI connection reports that limitation explicitly if one is selected.

For other providers, **OpenAI API Format** defaults to Auto: a URL ending in
`/responses` uses Responses; other URLs use Chat Completions. Select Responses
explicitly for a base URL when required. Model discovery always uses the
base URL's `/models` route.

Saving a changed API key or URL refreshes the main model selector and all
pipeline selectors from the same current catalog. Previous OpenAI pipeline
overrides reset when the connection changes. Empty lists and discovery errors
are shown in Settings and beside the main selectors; they do not reuse models
from the previous connection. Use **Refresh models** to retry discovery after
changing access in the provider account. Include the API path in the base URL
(for example, `https://api.justwoker.icu/v1`); a website homepage may return
HTML instead of a model catalog. A successful `/models` response with an empty
`data` list means the provider advertised no models for that key.

For OpenCode Zen's `muse-spark-1.3-contributor-free` example:

- URL: `https://opencode.ai/zen/v1`
- API format: Auto (OpenCode routes per model regardless of this setting)
- Responses reasoning effort: Extra high (`xhigh`), or Provider default
- Choose the model under OpenAI in the story selector and any desired pipeline
  model overrides (background analysis and rule refinement).

Responses requests send `input` and, when selected, `reasoning.effort`. They
omit the app's default sampling controls for compatibility with reasoning
models and set `store: false`. Only visible assistant text is saved; reasoning
items are excluded. Incomplete, failed, refused, or interrupted Responses are
reported as errors rather than accepted as completed output. Existing
Chat Completions configurations continue to use their original format.

These settings apply to the hosted OpenAI provider. The separate browser-direct
Local OpenAI-Compatible Server continues to use Chat Completions.

When a selected provider returns an error, Story Weaver preserves its HTTP
status for retry handling and displays its actual reason. A rate limit (429)
is shown as a rate limit during retries, rather than as an unavailable model.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/test_model_discovery_frontend.cjs
```

## Hosted deployment

Configure Firebase Admin credentials before exposing the application publicly. Provider API keys are stored per signed-in account through Settings; guests are read-only. Server-side custom OpenAI-compatible endpoints must use HTTPS and resolve only to public IP addresses. Leave `TRUST_PROXY_HEADERS=false` unless the app is behind a trusted proxy that overwrites the forwarded-client headers.
