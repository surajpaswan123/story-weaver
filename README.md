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
`data` list means the provider advertised no models for that key. Every provider
with a saved key remains in the Provider selector even if discovery fails or
returns no models. Select it to hear its connection status; when no catalog is
available, enter an exact **Model ID** supplied by that provider to generate a
story. A missing catalog alone does not establish whether generation works.
For OpenAI, the selected-provider status also displays the saved API URL. An
empty URL uses `https://api.openai.com/v1` for both discovery and generation.

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

## Regenerate with feedback

The latest completed turn has a **Regenerate with feedback** button. It opens a
labelled **Enter your feedback** textbox with submit and cancel controls. Submit
uses the normal undo operation, including the reference-file snapshot restore,
then sends the original prompt and normal story context with three added sections:
**Turn to replace**, **Model thoughts**, and **Feedback**. The replacement is saved
as the new turn; the feedback and discarded draft are not appended to story prose.

Thought tags actually returned by the model are saved separately in the chat
entry and included under **Model thoughts**, preserving their tags and contents.
They are also available in a collapsed Model thoughts section on saved turns.
Older turns whose thoughts were discarded cannot recover that missing text; the
regeneration states that no thoughts were saved. This feature does not request
or reconstruct reasoning that a provider never returned.

Feedback is preserved in the pending retry record after undo and on generation
failure, so Retry after a reload keeps the same revision instructions. The
feature supports hosted text generation and browser-direct local text models.
As with ordinary Regenerate, it replaces the latest completed turn.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/test_model_discovery_frontend.cjs tests/test_feedback_frontend.cjs
```

## Hosted deployment

Configure Firebase Admin credentials before exposing the application publicly. Provider API keys are stored per signed-in account through Settings; guests are read-only. Server-side custom OpenAI-compatible endpoints must use HTTPS and resolve only to public IP addresses. Leave `TRUST_PROXY_HEADERS=false` unless the app is behind a trusted proxy that overwrites the forwarded-client headers.

### Scheduled liveness ping

Use `https://story-weaver-m47x.onrender.com/ping` for a cron-job.org job:

- Method: **GET**.
- Schedule: **every 10 minutes**.
- Authentication, headers, and request body: none required.
- Expected response: HTTP **200**, plain text **OK** (2 bytes).

The endpoint also accepts HEAD, returning the same status and headers without a
body. It sends `Cache-Control: no-store` and performs no authentication, database,
story, or AI-provider work. Calling this endpoint reaches Story Weaver directly;
it does not launch another request to itself. This is a liveness check, not a
check that model providers or databases are available.

Use `/ping` instead of the homepage: [cron-job.org's FAQ](https://cron-job.org/en/faq/)
documents a 64 KB response limit and a 30-second execution timeout. The full
application page exceeds that response limit. Update and re-enable an existing
job if repeated failures disabled it.

[Render's free-service documentation](https://render.com/docs/free) says an idle
free web service sleeps after 15 minutes, and waking one can take about a minute.
A 10-minute schedule is intended to keep incoming requests below that idle
interval. An initial cold start or deployment restart can still exceed the cron
timeout; after the app has finished waking, subsequent pings can return the small
response. Regular pings do not override Render's restarts or account limits.
