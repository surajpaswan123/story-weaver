# Story Weaver

<p align="center">
  <strong>The Long-Form AI Novelist, Creative Writing Studio & Narrative Intelligence Engine</strong>
</p>

<p align="center">
  <a href="#-for-writers--storytellers-non-technical-guide"><strong>Writer's Guide (Non-Technical)</strong></a> •
  <a href="#-for-developers--engineers-technical-architecture"><strong>Developer's Blueprint (Technical)</strong></a> •
  <a href="#-quick-start-guide"><strong>Quick Start</strong></a> •
  <a href="#-custom-ai-models--providers"><strong>Model Routing</strong></a> •
  <a href="#-deployment--self-hosting"><strong>Deployment</strong></a> •
  <a href="#-rest--sse-api-reference"><strong>API Reference</strong></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Database-PostgreSQL%20%2F%20Neon-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Auth-Firebase%20%2F%20Local-FFCA28?style=flat-square&logo=firebase&logoColor=black" alt="Firebase Auth" />
  <img src="https://img.shields.io/badge/Docker-Container%20Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker Ready" />
  <img src="https://img.shields.io/badge/AI%20Models-Gemini%20%7C%20Claude%20%7C%20OpenAI%20%7C%20Ollama-7C3AED?style=flat-square" alt="Multi-Provider AI" />
</p>

---

## 📖 Table of Contents

- [Overview](#overview)
- [✨ For Writers & Storytellers (Non-Technical Guide)](#-for-writers--storytellers-non-technical-guide)
  - [What Makes Story Weaver Different?](#what-makes-story-weaver-different)
  - [Core Writing Features at a Glance](#core-writing-features-at-a-glance)
  - [Your Story Bible (The Reference Files)](#your-story-bible-the-reference-files)
  - [How "Regenerate with Feedback" Works](#how-regenerate-with-feedback-works)
  - [Speaking Your Story (Voice-to-Prose)](#speaking-your-story-voice-to-prose)
  - [Step-by-Step: Writing Your First Chapter](#step-by-step-writing-your-first-chapter)
- [⚡ Quick Start Guide](#-quick-start-guide)
  - [Running Locally on Windows (One-Click)](#running-locally-on-windows-one-click)
  - [Running Locally via Terminal (Windows, macOS, Linux)](#running-locally-via-terminal-windows-macos-linux)
  - [Local Super-Admin Mode (No Accounts or Cloud Setup Needed)](#local-super-admin-mode-no-accounts-or-cloud-setup-needed)
- [🧠 For Developers & Engineers (Technical Architecture)](#-for-developers--engineers-technical-architecture)
  - [System Architecture Diagram](#system-architecture-diagram)
  - [Multi-Provider Routing Engine](#multi-provider-routing-engine)
  - [Context Assembly & Recency Pipeline](#context-assembly--recency-pipeline)
  - [Diagnostic Isolation Architecture](#diagnostic-isolation-architecture)
  - [Streaming, Concurrency & Disconnect Survivability](#streaming-concurrency--disconnect-survivability)
  - [Virtual Sectioned File Editor (24k Char Viewport)](#virtual-sectioned-file-editor-24k-char-viewport)
  - [Storage Layer & ACID Transactional Persistence](#storage-layer--acid-transactional-persistence)
  - [Incremental JSON History Paging (ijson)](#incremental-json-history-paging-ijson)
  - [Security, Tenant Isolation & SSRF Mitigation](#security-tenant-isolation--ssrf-mitigation)
- [🔌 Custom AI Models & Providers](#-custom-ai-models--providers)
  - [Supported LLM Gateways](#supported-llm-gateways)
  - [OpenCode Zen Dynamic Routing](#opencode-zen-dynamic-routing)
  - [Anthropic Messages API Integration](#anthropic-messages-api-integration)
  - [Browser-Direct Local Models (Ollama, LM Studio, vLLM)](#browser-direct-local-models-ollama-lm-studio-vllm)
  - [Multi-Key Rotation & Key Masking](#multi-key-rotation--key-masking)
- [🛠️ Configuration & Environment Variables](#️-configuration--environment-variables)
- [🚀 Deployment & Self-Hosting](#-deployment--self-hosting)
  - [Docker Container](#docker-container)
  - [ClawCloud Run / Kubernetes](#clawcloud-run--kubernetes)
  - [Render Deployment & 24/7 Keep-Alive Liveness Probe](#render-deployment--247-keep-alive-liveness-probe)
- [📡 REST & SSE API Reference](#-rest--sse-api-reference)
- [🧪 Testing & Quality Assurance](#-testing--quality-assurance)
- [❓ Frequently Asked Questions (FAQ)](#-frequently-asked-questions-faq)
- [📄 License & Credits](#-license--credits)

---

## Overview

**Story Weaver** is an open-source, full-stack creative writing studio and long-form narrative intelligence engine. Unlike generic chat interfaces that suffer from memory amnesia, context drift, and plot hallucinations after a few thousand words, Story Weaver is engineered from the foundation up for **full-length novels, multi-chapter fiction, serialized episodic sagas, and interactive tabletop campaigns**.

It pairs frontier LLMs (Google Gemini, Anthropic Claude, OpenAI, Grok, DeepSeek, and local offline models) with an automated **Story Bible**, real-time **consistency tracking**, **transactional multi-file undo/redo**, and **resilient background generation**.

Whether you are an aspiring novelist with zero technical background who wants an intuitive AI co-author, or an AI engineer seeking an enterprise-grade reference architecture for multi-provider streaming, long-context management, and ACID-compliant story persistence, Story Weaver is designed for you.

---

## ✨ For Writers & Storytellers (Non-Technical Guide)

If you are an author, fiction writer, hobbyist, or game master with no technical or programming background, this section is designed specifically for you!

```
┌────────────────────────────────────────────────────────────────────────┐
│                              STORY WEAVER                              │
│                                                                        │
│   [ Story Bible ]          [ Author Studio ]        [ Smart Memory ]   │
│   • Characters             • Live Manuscript        • Never forgets    │
│   • World Rules            • Voice Recording          plot points      │
│   • Locations & Items      • Feedback Loops         • Tracks active    │
│   • Incident History       • Undo / Redo              character locs   │
└────────────────────────────────────────────────────────────────────────┘
```

### What Makes Story Weaver Different?

Standard AI chat apps treat writing like an ephemeral text chat: as the conversation lengthens, earlier details scroll out of memory. The AI forgets what happened in Chapter 1, alters a character's appearance, or resurrects a deceased antagonist.

**Story Weaver solves this completely:**

1. **Photographic Story Memory**: Designed specifically for modern 1M+ token context windows, Story Weaver delivers your complete manuscript, evolving summary, and reference sheets into the AI on every single turn.
2. **Dedicated Story Bible**: Your characters, physical positions, inventory, world rules, and timeline are stored in modular files that the AI studies before writing a single word.
3. **You Hold the Reins**: You can edit the manuscript directly at any time, adjust character sheets, undo unwanted turns with one click, or command the AI to revise a scene with specific creative feedback.
4. **Speak, Don't Just Type**: Have writer's block or prefer brainstorming out loud? Click the microphone button to dictate ideas. The AI transcribes your voice and transforms your spoken notes into vivid prose.
5. **Zero Vendor Lock-In**: Run 100% free and offline on your laptop with local models (Ollama / LM Studio), or plug in top-tier cloud models like Claude 3.5 Sonnet, Gemini 2.0 Flash, or GPT-4o.

---

### Core Writing Features at a Glance

| Feature | What It Does for You |
| :--- | :--- |
| **Long-Form Memory** | Automatically maintains continuity over hundreds of pages. Characters stay in character; established lore remains intact. |
| **Regenerate with Feedback** | Don't like how a scene turned out? Click one button, type *"Make the villain more menacing and reveal John's secret"*, and watch the AI seamlessly revise the scene. |
| **Story Bible Sidebar** | Quick-access tabs to view and edit your Characters, Locations, Rules, Items, and Timeline on the fly. |
| **Voice Dictation** | Record your voice directly inside the app to draft beats, dictate dialogue, or brainstorm out loud. |
| **Instant Undo / Redo** | Made a wrong turn? Hit Undo to restore both your story text and your reference files to the exact state before that turn. |
| **Distraction-Free Editor** | A clean, dark-mode writing interface with full search & replace, copy selection, full-file export, and keyboard shortcuts. |
| **Crash & Refresh Proof** | If your browser closes or your internet blips while the AI is generating, don't panic! The server keeps writing in the background and saves your work safely. |

---

### Your Story Bible (The Reference Files)

Inside every story, Story Weaver automatically organizes your narrative universe into modular, easy-to-read markdown files. You can let the AI maintain them automatically, or open and edit them whenever you wish:

* **`story.md`**: Your complete, continuous book manuscript.
* **`characters.md`**: Character dossiers, personalities, physical traits, backstories, and relationships.
* **`positions.md`**: Where everyone is located **right now**. The AI prioritizes this over older mentions so characters don't magically teleport across kingdoms.
* **`locations.md`**: Cities, taverns, planets, rooms, and environmental atmosphere.
* **`items.md`**: Crucial artifacts, weapons, keys, documents, and who currently possesses them.
* **`villains.md`**: Antagonists, motivations, schemes, and threat levels.
* **`incidents.md`**: A chronological record of major narrative events and plot turning points that actually occurred.
* **`time.md`**: The narrative timeline (day, hour, season, chronology).
* **`style.md`**: Your authorial voice instructions (e.g., *"Third-person limited, gritty noir tone, avoid clichés, focus on sensory prose"*).
* **`summary.md`**: A living, evolving synopsis of everything that has unfolded so far.
* **`consistency.md`**: An automated diagnostic audit that spots timeline or logic paradoxes for you without cluttering the AI's creative train of thought.

---

### How "Regenerate with Feedback" Works

Traditional chatbots force you to either delete everything or argue with the AI in new messages when a scene misses the mark. 

In Story Weaver:
1. Locate the latest AI response in your story history.
2. Click **Regenerate with feedback**.
3. Enter your critique in plain English:
   > *"Everything was great, but keep Sarah silent during the argument, and make the ending more suspenseful."*
4. Story Weaver automatically:
   - Rolls back the story manuscript and reference files to the moment before the turn.
   - Packages your feedback, the discarded draft, and any AI reasoning thoughts into a special revision guide.
   - Prompts the model to craft a fresh, targeted revision without leaving any meta-conversation or feedback text inside your final manuscript!

---

### Speaking Your Story (Voice-to-Prose)

1. Click the **Microphone** icon beside the prompt box.
2. Speak naturally: describe the scene, dictate dialogue, or brainstorm a plot twist.
3. Stop recording. Multimodal AI models (such as Gemini 2.0 or GPT-4o Audio) transcribe your audio and immediately synthesize it into vivid literary narrative matching your book's existing style.

---

### Step-by-Step: Writing Your First Chapter

1. **Launch the App**: Open `http://127.0.0.1:8000` in your web browser.
2. **Create a Story**: Click **New Story**, give it a title, and write a brief starting premise (e.g., *"A detective investigates a vanishing airship over Neo-London"*).
3. **Choose Your AI**: Select your preferred AI model from the dropdown (or configure your API keys in the ⚙️ **Settings** menu).
4. **Enter Your First Beat**: Type what happens next or provide high-level direction:
   > *"Begin Chapter 1 on the foggy docks. Detective Vance arrives at the crime scene and meets Inspector Cross."*
5. **Watch the Story Unfold**: The AI streams high-quality prose directly into your manuscript while quietly updating your character dossiers, incident logs, and timeline in the background.

---

## ⚡ Quick Start Guide

### Running Locally on Windows (One-Click)

1. Clone or download this repository.
2. Double-click **`Start_Story_Weaver.bat`**.
   - The batch script automatically checks your environment, activates the virtual environment, installs dependencies, and launches the web app.
3. Open **`http://127.0.0.1:8000`** in your browser.

---

### Running Locally via Terminal (Windows, macOS, Linux)

```bash
# 1. Clone the repository
git clone https://github.com/surajpaswan123/story-weaver.git
cd story-weaver

# 2. Create and activate a Python virtual environment
python -m venv .venv

# On Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# On macOS / Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the server
python main.py
```

The FastAPI application will start listening on `http://127.0.0.1:8000`.

---

### Local Super-Admin Mode (No Accounts or Cloud Setup Needed)

If you want to run Story Weaver locally on your computer without setting up Firebase Authentication or a cloud database:

Create a `.env` file in the root directory:
```env
ALLOW_LOCAL_SUPER_ADMIN=true
ALLOW_UNVERIFIED_JWT=true
PORT=8000
HOST=127.0.0.1
```

When `ALLOW_LOCAL_SUPER_ADMIN=true` is set, Story Weaver bypasses all external login requirements and automatically grants full access with local file-based storage in `./stories`.

---

## 🧠 For Developers & Engineers (Technical Architecture)

This section provides an exhaustive technical breakdown of Story Weaver's architecture, runtime models, concurrency patterns, and storage mechanisms.

### System Architecture Diagram

```mermaid
flowchart TB
    subgraph Client ["Client Layer (Browser SPA)"]
        UI["Vanilla JS / HTML5 / Tailwind CSS"]
        VEditor["Sectioned Virtual File Editor (24k Char Windows)"]
        SSEListener["SSE Stream Consumer & Heartbeat Listener"]
        DirectLocal["Browser-Direct Local AI (Ollama / LM Studio)"]
    end

    subgraph Backend ["Backend Layer (FastAPI / Python)"]
        Router["FastAPI Application (main.py)"]
        AuthMiddleware["Tenant & Auth Guard (Firebase Admin / Local Super-Admin)"]
        TurnMgr["TurnProgress In-Memory Concurrency & Locks"]
        RouterHub["Multi-Provider AI Router (openai_compat.py)"]
        ContextAssembler["Context Pipeline & Recency Assembler"]
        HistoryPaginator["ijson Incremental Transcript Parser"]
        LivenessProbe["/ping Liveness Probe (Zero I/O, <5ms)"]
    end

    subgraph Storage ["Persistence Layer"]
        PG[(PostgreSQL / Neon ACID Primary Store)]
        FSFallback[(Firestore Legacy Fallback)]
        DiskCache[("Local Disk Cache: /stories/{uid}/{story_id}")]
    end

    subgraph Providers ["AI Providers & Gateways"]
        GeminiSDK["Google GenAI SDK (google-genai)"]
        AnthropicAPI["Anthropic Messages API (Native / v1/messages)"]
        OpenAIGateway["OpenAI Chat & Responses Protocols"]
        OpenCodeZen["OpenCode Zen Dynamic Protocol Engine"]
        CloudGroq["Groq / OpenRouter / NVIDIA NIM"]
    end

    UI -->|HTTP / REST| Router
    UI -->|Server-Sent Events| SSEListener
    DirectLocal -.->|Direct Localhost CORS| UI
    Router --> AuthMiddleware
    AuthMiddleware --> TurnMgr
    TurnMgr --> ContextAssembler
    ContextAssembler --> RouterHub
    RouterHub --> GeminiSDK
    RouterHub --> AnthropicAPI
    RouterHub --> OpenAIGateway
    RouterHub --> OpenCodeZen
    RouterHub --> CloudGroq
    TurnMgr -->|Atomic Multi-File Commit| PG
    PG -.->|Initial Import Fallback| FSFallback
    TurnMgr -->|Local Sync| DiskCache
    Router --> HistoryPaginator
    HistoryPaginator --> PG
```

---

### Multi-Provider Routing Engine

Story Weaver features a custom-built protocol abstraction layer located in `openai_compat.py`. It transparently adapts disparate LLM protocols into unified asynchronous Python generators:

1. **Google GenAI SDK**: Uses `google.genai` for Gemini 1.5 Pro, 2.0 Flash, and native multimodal audio streaming.
2. **Anthropic Messages API**:
   - Native HTTP client utilizing `x-api-key`, `anthropic-version: 2023-06-01`.
   - Top-level `system` prompt separation with structured user/assistant turns.
   - Configurable token ceilings (up to 131,072 output tokens) with graceful fallback to provider advertised maximums.
   - Dynamic model discovery with cursor-based pagination.
3. **OpenAI Chat Completions API**: Standard `/chat/completions` protocol with streaming SSE deltas.
4. **OpenAI Responses API**: Full support for the newer `/responses` protocol, including configurable reasoning effort (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`) and output text extraction while discarding non-text reasoning frames.
5. **OpenCode Zen Intelligent Routing**: Automatically detects `https://opencode.ai/zen/v1` and partitions requests by model family:
   - `muse-spark-*`, `gpt-*`, `grok-*` -> Responses API
   - `claude-*`, `qwen*` -> Anthropic Messages API
   - `mimo-*`, `deepseek-*`, `glm-*`, `minimax-*` -> Chat Completions API
   - `gemini-*` -> Google Native protocol validation

---

### Context Assembly & Recency Pipeline

In long-form generative fiction, attention degradation over long context windows is a known vulnerability. Story Weaver counters this by employing a **strict reciprocal attention ordering**:

```
[System Constraints & Writing Rules (rules.md)]
      ↓
[Worldbuilding & Lore Bibles (characters.md, positions.md, locations.md, items.md, villains.md)]
      ↓
[Audio Log & Stylistic Guide (audio_log.md, style.md)]
      ↓
[Narrative Timeline & Synoptic Beats (time.md, summary.md)]
      ↓
[Continuous Story Manuscript (story.md)]  <-- Placed closest to the generation point
      ↓
[Active Turn Prompt / Feedback Context]
```

By placing the actual continuous prose of `story.md` immediately adjacent to the completion point, the model's self-attention heads prioritize recent stylistic cadence, vocabulary, and scene pacing over background reference material.

---

### Diagnostic Isolation Architecture

A frequent pathology in AI writing tools is **diagnostic hallucination leakage**: when an automated validator flags an error (e.g., *"Character X was in London in Chapter 2, but appears in Paris in Chapter 3"*), the model mistakenly treats the error message as story prose and incorporates diagnostic meta-commentary into the novel.

Story Weaver isolates diagnostics via `SKIP_FILES`:
```python
SKIP_FILES = {"rules.md", "context.md", "story.md", "consistency.md"}
```

* `consistency.md` is generated by an automated consistency validator for human review.
* It is preserved through transactional undo/redo and file editing.
* **It is strictly omitted from the model's generation prompt**, ensuring zero context pollution.

---

### Streaming, Concurrency & Disconnect Survivability

Unlike conventional web applications where closing a browser tab triggers an immediate `SIGINT` or task cancellation that corrupts in-flight files, Story Weaver implements **Asynchronous Disconnect Survivability**:

1. **Process-Local Locking (`TurnProgress`)**:
   - Each story is protected by a thread-safe re-entrant lock (`threading.RLock()`) keyed by `(user_id, story_id)`.
   - Prevents race conditions, double-submissions, and interleaving file writes.
2. **Worker Independence**:
   - The generation pipeline runs inside an asynchronous background task.
   - Text chunks are dispatched to a bounded queue (`queue.Queue(maxsize=100)`) consumed by the SSE streaming generator.
   - If the user closes the tab, loses Wi-Fi, or refreshes the page, the consumer stream closes cleanly, but the **background worker keeps running until completion**, cleanly committing the finished turn and file snapshots to PostgreSQL.
3. **Live Turn Status Polling (`/story/{id}/generation-status`)**:
   - Reopening the page queries the lightweight status endpoint.
   - Status states: `starting` -> `generating` -> `retrying` -> `finalizing` -> `completed` / `failed` / `stopped`.
   - Polling frequency is automatically throttled (3s when active, 15s in background tabs).
   - Prompts and generated text are never stored in status records, keeping memory overhead negligible.

---

### Virtual Sectioned File Editor (24k Char Viewport)

Browsers suffer severe layout thrashing and DOM slowdowns when rendering monolithic text documents containing 100,000+ words inside a standard `<textarea>`.

Story Weaver implements a zero-dependency **Sectioned Virtual File Viewport** in `static/file-editor.js`:
* **24,000-Character Viewport Windows**: Large files are transparently split into navigable viewports.
* **Bounded Layout Cost**: The browser DOM only renders a single section at a time, eliminating typing lag and cursor jitter.
* **Atomic Global Operations**: 
  - `Ctrl + A` and **Copy All** grab the entire multi-million character file.
  - **Find & Replace** searches across section boundaries.
  - **Save** and **Download** always commit the complete, assembled document.
* **Diff-Based Undo Stack**: In-memory edit history stores character deltas rather than full-document clones, capping memory consumption at 20 MiB for up to 500 undo operations.

---

### Storage Layer & ACID Transactional Persistence

Story Weaver provides enterprise-grade persistence backed by PostgreSQL (e.g., Neon Serverless Postgres) with automatic schema provisioning:

```sql
CREATE TABLE IF NOT EXISTS user_keys (
    uid VARCHAR(255) PRIMARY KEY,
    keys JSONB NOT NULL,
    updated_at DOUBLE PRECISION DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_stories (
    uid VARCHAR(255) NOT NULL,
    story_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    title VARCHAR(255),
    PRIMARY KEY (uid, story_id, file_name)
);
```

#### Key Persistence Guarantees:
* **Single-Transaction Atomic Saves**: When a story turn completes, all modified reference files (`story.md`, `summary.md`, `characters.md`, `chat_log.json`, etc.) are written inside a **single SQL transaction (`conn.commit()`)**. If an upload fails midway, the entire transaction rolls back, preventing partial file state corruption.
* **Automatic Firestore Legacy Migration**: On the first read of a story, the engine checks PostgreSQL. If empty, it automatically migrates existing documents from Google Cloud Firestore without data loss.
* **Local Caching Layer**: Files are cached locally in `./stories/{uid}/{story_id}/` for instant sub-millisecond retrieval.

---

### Incremental JSON History Paging (`ijson`)

Chat logs for novels can grow to dozens of megabytes. Parsing massive JSON transcripts with Python's standard `json.loads()` causes severe memory spikes and latency.

Story Weaver uses `ijson` for **incremental stream-parsing** in `runtime_support.py`:
* `GET /story/{story_id}/chat` reads messages lazily from disk or database streams.
* Returns paged batches (default 40 turns) bounded by a soft 256,000-character budget.
* Employs optimistic concurrency revision tokens: if history changes during paging, the server returns an HTTP `409 Conflict`, prompting the UI to synchronize cleanly.

---

### Security, Tenant Isolation & SSRF Mitigation

1. **Strict SSRF Mitigation**: When users configure custom OpenAI-compatible base URLs, Story Weaver resolves hostnames and verifies target IP addresses before dispatching HTTP requests:
   - Blocks private, loopback, link-local, and multicast ranges (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`).
   - Rejects non-HTTP(S) schemes.
2. **Tenant Isolation**: Every API endpoint enforces authentication via Firebase Admin cryptographically verified JWT tokens. All SQL queries and file paths are strictly scoped to the authenticated user's `uid`.
3. **Fail-Closed Production Deployment**: `ALLOW_UNVERIFIED_JWT` and `ALLOW_LOCAL_SUPER_ADMIN` are strictly prohibited in production containers (`HOST=0.0.0.0`). Unauthenticated requests fail closed with HTTP `401 / 403`.

---

## 🔌 Custom AI Models & Providers

### Supported LLM Gateways

Story Weaver allows you to mix and match different AI providers for different pipeline stages:
* **Story Writer Model**: The primary author of prose.
* **Background Analysis Model**: Periodically updates character bibles, timeline, and lore.
* **Rules Refinement Model**: Polishes formatting, stylistic tone, and rules constraints.
* **Audio Model**: Transcribes and processes voice recordings.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        SUPPORTED AI PROVIDERS                          │
│                                                                        │
│   • Google Gemini (Gemini 2.0 Flash / Pro, Gemini 1.5 Pro)             │
│   • Anthropic (Claude 3.5 Sonnet, Claude 3 Opus, Claude 3.5 Haiku)     │
│   • OpenAI (GPT-4o, GPT-4.5, o1, o3-mini)                             │
│   • OpenCode Zen (Dynamic protocol switching)                          │
│   • OpenRouter (Access 200+ models via unified key)                    │
│   • Groq (Ultra-low-latency Llama 3.3, Mixtral)                        │
│   • NVIDIA NIM (DeepSeek-V3, Llama-3.1-405B)                           │
│   • Local Offline Models (Ollama, LM Studio, vLLM via browser-direct)  │
└────────────────────────────────────────────────────────────────────────┘
```

---

### OpenCode Zen Dynamic Routing

For users accessing models through **OpenCode Zen** (`https://opencode.ai/zen/v1`), Story Weaver automatically negotiates the underlying protocol:
* **Responses Protocol**: `muse-spark-*` (including Contributor Free), `gpt-*`, `grok-*`.
* **Anthropic Messages Protocol**: `claude-*`, `qwen*`.
* **Chat Completions Protocol**: `deepseek-*`, `mimo-*`, `glm-*`, `minimax-*`.
* **Reasoning Effort Control**: Supports `xhigh`, `high`, `medium`, `low`, or `none`.

---

### Anthropic Messages API Integration

To connect Anthropic directly or through a reverse proxy:
1. Open **Settings** (⚙️).
2. Enter your API Key (`sk-ant-...`).
3. Set the Endpoint URL:
   - Direct: `https://api.anthropic.com/v1/messages`
   - Custom Gateway: `https://your-gateway.com/v1/messages`
4. Set optional **Maximum Output Tokens** (defaults to advertised catalog maximum, or up to 131,072).
5. Visible text blocks stream into your manuscript, while internal thinking tags are preserved cleanly in the chat transcript.

---

### Browser-Direct Local Models (Ollama, LM Studio, vLLM)

For 100% free, private, offline generation:
1. Start your local OpenAI-compatible server:
   - **Ollama**: `ollama run llama3.3` (runs on `http://localhost:11434/v1`)
   - **LM Studio**: Start Local Server on `http://localhost:1234/v1`
2. In Story Weaver, select **Local OpenAI-Compatible Server**.
3. **Zero Backend Overhead**: The browser communicates directly with your local server via CORS. No prompts, manuscripts, or tokens pass through the Python backend!

---

### Multi-Key Rotation & Key Masking

In the Settings modal, you can configure multiple API keys for each provider:
* **Key Masking**: Saved keys are never sent back to the browser in plaintext; only masked indicators (`sk-...XXXX`) are displayed.
* **Failover & Load Balancing**: The backend automatically rotates between configured keys to distribute rate limits.

---

## 🛠️ Configuration & Environment Variables

Configure Story Weaver using a `.env` file or container environment variables:

| Variable | Type | Default | Description |
| :--- | :---: | :---: | :--- |
| `DATABASE_URL` | String | *None* | PostgreSQL connection string (Neon, Supabase, or self-hosted Postgres). |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | String | *None* | Raw JSON string of the Firebase Admin service account credentials. |
| `FIREBASE_CREDENTIALS_FILE` | String | `firebase-credentials.json` | Path to a local Firebase Admin service account JSON file. |
| `ALLOW_LOCAL_SUPER_ADMIN` | Boolean | `false` | When `true`, enables unauthenticated local super-admin mode for single-user offline desktop usage. |
| `ALLOW_UNVERIFIED_JWT` | Boolean | `false` | Allows decoding unverified JWTs when running on unhosted local instances without Firebase Admin. Fails closed if hosted. |
| `HOST` | String | `127.0.0.1` | Network interface to bind the Uvicorn web server (`0.0.0.0` for Docker/cloud). |
| `PORT` | Integer | `8000` | Port for the HTTP server. |
| `RELOAD` | Boolean | `false` | Enables Uvicorn hot-reloading during development. |
| `TRUST_PROXY_HEADERS` | Boolean | `false` | Set to `true` ONLY if running behind a trusted reverse proxy (e.g., Nginx, Cloudflare) that overwrites client IP headers. |
| `GEMINI_API_KEY` | String | *None* | Fallback system Gemini API key if not provided by user settings. |
| `OPENAI_API_KEY` | String | *None* | Fallback system OpenAI API key. |

---

## 🚀 Deployment & Self-Hosting

### Docker Container

Story Weaver includes an optimized multi-stage `Dockerfile`:

```bash
# Build the Docker image
docker build -t story-weaver .

# Run the container
docker run -d \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:password@ep-cool-pool.neon.tech/neondb?sslmode=require" \
  -e FIREBASE_SERVICE_ACCOUNT_JSON='{"type": "service_account", ...}' \
  -v story_data:/app/stories \
  --name story-weaver-app \
  story-weaver
```

Published images are also available directly via GitHub Container Registry:
```bash
docker pull ghcr.io/surajpaswan123/story-weaver:main
```

---

### ClawCloud Run / Kubernetes

Refer to `docs/clawcloud.md` for full deployment instructions on ClawCloud Run:
* **Recommended Sizing**: 0.5 vCPU, 1 GB RAM (Fixed 1 instance because story locks and active turn states are process-local).
* **Port**: `8000` (HTTP).
* **Health Check**: `GET /ping` on port 8000.

---

### Render Deployment & 24/7 Keep-Alive Liveness Probe

When hosting on free platforms like Render where idle containers sleep after 15 minutes:

1. Deploy Story Weaver as a Web Service.
2. Set up a free monitoring check at [cron-job.org](https://cron-job.org/):
   - **Target URL**: `https://your-app.onrender.com/ping`
   - **Method**: `GET` or `HEAD`
   - **Schedule**: Every 10 minutes
   - **Response**: HTTP 200 `OK` (2 bytes, zero database queries, zero AI API costs).

> [!TIP]
> Always ping `/ping` rather than `/`. The homepage HTML and assets exceed cron-job.org's 64 KB response limit and cause false timeout alarms, whereas `/ping` responds in < 5 milliseconds.

---

## 📡 REST & SSE API Reference

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/ping` | Lightweight liveness probe. Returns HTTP 200 `OK` (2 bytes). No auth. |
| `GET` | `/stories` | List all stories owned by the authenticated user. |
| `POST` | `/stories/create` | Create a new story with initial title, premise, and Story Bible templates. |
| `DELETE` | `/story/{story_id}` | Permanently delete a story, its database records, and local cache. |
| `GET` | `/story/{story_id}` | Retrieve story metadata, word count, and file manifest. |
| `GET` | `/story/{story_id}/full` | Fetch the complete manuscript (`story.md`). |
| `GET` | `/story/{story_id}/chat` | Fetch paged chat transcript (supports `last`, `before`, `after`, and `revision`). |
| `GET` | `/story/{story_id}/generation-status` | Poll the current background generation status (`generating`, `finalizing`, `completed`, etc.). |
| `POST` | `/generate` | Primary story generation endpoint. Dispatches background worker and streams SSE events. |
| `POST` | `/story/{story_id}/stop` | Immediately cancel active generation for this story. |
| `POST` | `/story/{story_id}/undo` | Atomic undo: rolls back manuscript, reference files, and transcript to previous turn snapshot. |
| `POST` | `/story/{story_id}/retry` | Retry the last failed or interrupted generation turn. |
| `POST` | `/generate-audio` | Upload audio recording for transcription and story synthesis. |
| `GET` | `/story/{story_id}/files` | List all markdown reference files inside the Story Bible. |
| `GET` | `/story/{story_id}/file/{filename}` | Retrieve raw content of a specific reference file. |
| `PUT` | `/story/{story_id}/file/{filename}` | Update raw content of a reference file. |
| `DELETE` | `/story/{story_id}/file/{filename}` | Delete a custom reference file. |
| `GET` | `/api/providers-models` | Query live catalog discovery across all configured AI providers. |
| `GET` | `/api/user/settings` | Retrieve user settings and masked API keys. |
| `POST` | `/api/user/settings` | Save user API keys, custom endpoints, and pipeline model preferences. |
| `GET` | `/api/logs` | View recent server-side interceptor log buffer (debug utility). |

---

## 🧪 Testing & Quality Assurance

Story Weaver maintains rigorous unit and end-to-end integration test suites covering Python backend logic, streaming mechanics, and client-side DOM behaviors:

```powershell
# 1. Install development dependencies
pip install -r requirements-dev.txt

# 2. Run backend Python test suite
python -m pytest -q

# 3. Run frontend Node.js integration tests
node --test tests/test_model_discovery_frontend.cjs `
            tests/test_feedback_frontend.cjs `
            tests/test_chat_log_frontend.cjs `
            tests/test_file_editor.cjs
```

### Test Coverage Highlights
* **File Editor**: Verifies that 2,000,000-character documents traverse viewports without data loss, that Ctrl+A and clipboard operations remain atomic, and that undo/redo delta stacks function cleanly across section boundaries.
* **Feedback Engine**: Verifies single-undo guarantees, snapshot restoration, and prompt injection semantics.
* **Catalog Discovery**: Confirms race-condition immunity when switching providers rapidly in the UI.
* **Disconnect Recovery**: Validates that worker threads complete and sync to Postgres even after SSE streams are terminated.

---

## ❓ Frequently Asked Questions (FAQ)

<details>
<summary><strong>Q: Can I write NSFW or dark fantasy stories?</strong></summary>
<br />
Yes! While hosted models (like OpenAI or Claude) enforce their respective provider safety filters, you can connect uncensored open-weight models (such as Llama 3, Mistral, or Starcoder) running locally via Ollama or LM Studio. Story Weaver applies zero censorship on the application layer.
</details>

<details>
<summary><strong>Q: Will my stories be used to train AI models?</strong></summary>
<br />
No. Story Weaver connects directly to official enterprise API endpoints where training on API data is disabled by default. If you use local models via Ollama or LM Studio, your stories never leave your local physical machine.
</details>

<details>
<summary><strong>Q: How long can a story get before the app slows down?</strong></summary>
<br />
Story Weaver has been tested with manuscripts exceeding 200,000 words (over 1.5 million characters). Thanks to the 24,000-character sectioned editor, the browser never bogs down, and the backend leverages 1M+ token context windows seamlessly.
</details>

<details>
<summary><strong>Q: What happens if my internet disconnects mid-generation?</strong></summary>
<br />
Your work is safe! The server continues executing the story generation in the background. When your connection returns, simply reload the page—Story Weaver reconnects to the turn status and renders the completed chapter.
</details>

---

## 📄 License & Credits

* **Author**: [Suraj Paswan](https://github.com/surajpaswan123)
* **License**: MIT License. Open-source and free for personal, academic, and commercial creative writing.

<p align="center">
  <sub>Crafted with passion for novelists, worldbuilders, and storytellers everywhere.</sub>
</p>
