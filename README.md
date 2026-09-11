# Story Weaver

<p align="center">
  <strong>The Definitive Long-Form AI Novelist, Creative Writing Studio & Narrative Intelligence Engine</strong>
</p>

<p align="center">
  <a href="#-for-writers--storytellers-non-technical-guide"><strong>Writer's Guide</strong></a> •
  <a href="#-the-story-bible-specification-file-by-file-reference"><strong>Story Bible Spec</strong></a> •
  <a href="#-keyboard-shortcuts-cheat-sheet"><strong>Shortcuts</strong></a> •
  <a href="#-anatomy-of-a-story-turn-microsecond-lifecycle-trace"><strong>Turn Anatomy</strong></a> •
  <a href="#-storage-engine--sql-architecture"><strong>SQL & Storage</strong></a> •
  <a href="#-local-models--provider-cookbook"><strong>Local AI & Models</strong></a> •
  <a href="#-deployment--hosting-playbooks"><strong>Hosting Playbooks</strong></a> •
  <a href="#-rest--sse-api-reference"><strong>API Reference</strong></a> •
  <a href="#-complete-http-error--troubleshooting-dictionary"><strong>Troubleshooting</strong></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Database-PostgreSQL%20%2F%20Neon-336791?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Auth-Firebase%20%2F%20Local-FFCA28?style=flat-square&logo=firebase&logoColor=black" alt="Firebase Auth" />
  <img src="https://img.shields.io/badge/Docker-Container%20Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker Ready" />
  <img src="https://img.shields.io/badge/AI%20Models-Gemini%20%7C%20Claude%20%7C%20OpenAI%20%7C%20Ollama-7C3AED?style=flat-square" alt="Multi-Provider AI" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="MIT License" />
</p>

---

## 📖 Master Table of Contents

- [1. Executive Overview & Design Philosophy](#1-executive-overview--design-philosophy)
- [2. ✨ For Writers & Storytellers (Non-Technical Guide)](#2--for-writers--storytellers-non-technical-guide)
  - [What Makes Story Weaver Different?](#what-makes-story-weaver-different)
  - [Core Writing Features at a Glance](#core-writing-features-at-a-glance)
  - [The Story Bible at a Glance](#the-story-bible-at-a-glance)
  - [How "Regenerate with Feedback" Works](#how-regenerate-with-feedback-works)
  - [Speaking Your Story (Voice Dictation & Audio Logs)](#speaking-your-story-voice-dictation--audio-logs)
  - [Background Lore Analysis & Story Repair](#background-lore-analysis--story-repair)
  - [Step-by-Step: Writing Your First Chapter](#step-by-step-writing-your-first-chapter)
- [3. ⌨️ Keyboard Shortcuts Cheat Sheet](#3-️-keyboard-shortcuts-cheat-sheet)
- [4. 📚 The Story Bible Specification (File-by-File Reference)](#4--the-story-bible-specification-file-by-file-reference)
  - [1. story.md (The Master Manuscript)](#1-storymd-the-master-manuscript)
  - [2. characters.md (Character Dossiers & Relations)](#2-charactersmd-character-dossiers--relations)
  - [3. positions.md (Current Physical Locations)](#3-positionsmd-current-physical-locations)
  - [4. locations.md (World Atlas & Spatial Settings)](#4-locationsmd-world-atlas--spatial-settings)
  - [5. items.md (Inventory & Artifact Tracking)](#5-itemsmd-inventory--artifact-tracking)
  - [6. villains.md (Antagonists & Factions)](#6-villainsmd-antagonists--factions)
  - [7. incidents.md (Canonical Event Ledger)](#7-incidentsmd-canonical-event-ledger)
  - [8. time.md (Timeline & Chronology)](#8-timemd-timeline--chronology)
  - [9. style.md (Authorial Voice & Pacing)](#9-stylemd-authorial-voice--pacing)
  - [10. summary.md (Rolling Plot Synopsis)](#10-summarymd-rolling-plot-synopsis)
  - [11. rules.md (Hard Narrative Constraints)](#11-rulesmd-hard-narrative-constraints)
  - [12. consistency.md (Automated Diagnostic Audit)](#12-consistencymd-automated-diagnostic-audit)
  - [13. audio_log.md (Acoustic & Musical Memory)](#13-audio_logmd-acoustic--musical-memory)
  - [14. chat_log.json (Structured Turn History)](#14-chat_logjson-structured-turn-history)
- [5. ⚡ Quick Start Guide](#5--quick-start-guide)
  - [Method 1: Windows One-Click Batch Script](#method-1-windows-one-click-batch-script)
  - [Method 2: Cross-Platform Terminal (macOS, Linux, Windows)](#method-2-cross-platform-terminal-macos-linux-windows)
  - [Method 3: Local Super-Admin Desktop Mode (Zero Cloud)](#method-3-local-super-admin-desktop-mode-zero-cloud)
- [6. 🔬 Anatomy of a Story Turn (Microsecond Lifecycle Trace)](#6--anatomy-of-a-story-turn-microsecond-lifecycle-trace)
- [7. 🧠 Technical Architecture & Engineering Deep-Dive](#7--technical-architecture--engineering-deep-dive)
  - [High-Level Architecture Diagram](#high-level-architecture-diagram)
  - [Multi-Provider Protocol Unification (openai_compat.py)](#multi-provider-protocol-unification-openai_compatpy)
  - [Token Attention Ordering & Reciprocal Recency](#token-attention-ordering--reciprocal-recency)
  - [The 3-Stage Media Pipeline (Audio Processing)](#the-3-stage-media-pipeline-audio-processing)
  - [Diagnostic Isolation Architecture](#diagnostic-isolation-architecture)
  - [Streaming, Concurrency & Disconnect Survivability](#streaming-concurrency--disconnect-survivability)
  - [Virtual Sectioned File Viewport (24k Char Windows)](#virtual-sectioned-file-viewport-24k-char-windows)
  - [Chat History JSON Schema & Validation Engine](#chat-history-json-schema--validation-engine)
  - [Incremental JSON History Streaming (ijson)](#incremental-json-history-streaming-ijson)
  - [Live Server Log Interceptor & Slide-Out Panel](#live-server-log-interceptor--slide-out-panel)
  - [Accessibility (a11y) & Screen-Reader Architecture](#accessibility-a11y--screen-reader-architecture)
- [8. 💾 Storage Engine & SQL Architecture](#8--storage-engine--sql-architecture)
  - [Relational Schema (PostgreSQL / Neon)](#relational-schema-postgresql--neon)
  - [Single-Transaction Atomic Multi-File Commits](#single-transaction-atomic-multi-file-commits)
  - [Zero-Loss Legacy Firestore Migration](#zero-loss-legacy-firestore-migration)
  - [Local Caching Layer (/stories/{uid}/{story_id})](#local-caching-layer-storiesuidstory_id)
  - [Database Backup & Disaster Recovery Commands](#database-backup--disaster-recovery-commands)
- [9. 🔌 Local Models & Provider Cookbook](#9--local-models--provider-cookbook)
  - [1. Connecting Local Models (Ollama, LM Studio, vLLM)](#1-connecting-local-models-ollama-lm-studio-vllm)
  - [2. Anthropic Messages API (Direct & Gateway)](#2-anthropic-messages-api-direct--gateway)
  - [3. Google Gemini (Native google-genai SDK)](#3-google-gemini-native-google-genai-sdk)
  - [4. OpenCode Zen Dynamic Protocol Routing](#4-opencode-zen-dynamic-protocol-routing)
  - [5. OpenAI Chat Completions & Responses Protocols](#5-openai-chat-completions--responses-protocols)
  - [6. Groq, NVIDIA NIM, and OpenRouter](#6-groq-nvidia-nim-and-openrouter)
  - [7. Rate-Limit Resilience & 429 Exponential Backoff](#7-rate-limit-resilience--429-exponential-backoff)
  - [8. Multi-Key Rotation & Key Masking](#8-multi-key-rotation--key-masking)
- [10. 🚀 Deployment & Hosting Playbooks](#10--deployment--hosting-playbooks)
  - [Playbook A: Docker & Docker Compose](#playbook-a-docker--docker-compose)
  - [Playbook B: ClawCloud Run Deployment](#playbook-b-clawcloud-run-deployment)
  - [Playbook C: Render Web Service + 24/7 cron-job.org Ping](#playbook-c-render-web-service--247-cron-joborg-ping)
  - [Playbook D: Linux Production Deployment with systemd](#playbook-d-linux-production-deployment-with-systemd)
  - [Playbook E: Windows Auto-Start via Task Scheduler](#playbook-e-windows-auto-start-via-task-scheduler)
- [11. 📡 REST & SSE API Reference](#11--rest--sse-api-reference)
- [12. ⚠️ Complete HTTP Error & Troubleshooting Dictionary](#12-️-complete-http-error--troubleshooting-dictionary)
- [13. 🧪 Testing & Quality Assurance Suite](#13--testing--quality-assurance-suite)
- [14. ❓ Frequently Asked Questions (FAQ)](#14--frequently-asked-questions-faq)
- [15. 📄 License & Credits](#15--license--credits)


---

## 1. Executive Overview & Design Philosophy

Generating cohesive, multi-chapter fiction using large language models is fundamentally different from building conversational chatbots or coding assistants. Novel-length generation reveals critical failure modes in standard AI toolchains:

1. **Context Rot & Narrative Amnesia**: Conversational chat buffers drop early messages as the token limit is reached. The AI forgets essential world rules, character relationships, and earlier story turns.
2. **Diagnostic Hallucination Leakage**: When background checkers flag an error (e.g., *"Warning: Mark cannot hold the dagger because he dropped it in Chapter 4"*), typical prompting pipelines allow the model to incorporate the diagnostic reprimand directly into the story's prose.
3. **Fragile Generation Pipelines**: If an author loses internet connectivity or closes their browser tab during an 8,000-word generation turn, traditional applications cancel the server process mid-flight, leaving the manuscript half-written or corrupted.
4. **Client-Side DOM Choke**: Web browsers experience severe layout thrashing and input lag when rendering 200,000+ words in standard textareas or rich-text editors.
5. **Vendor & Hardware Lock-In**: Many authoring suites tether users to proprietary cloud providers, preventing the use of uncensored open-source models running locally.

**Story Weaver** was designed specifically to eliminate these bottlenecks. It is built as a **resilient narrative operating system** pairing modern 1M+ token context architectures with an automated Story Bible, ACID-compliant multi-file persistence, a virtual sectioned DOM editor, and protocol-agnostic model routing.

---

## 2. ✨ For Writers & Storytellers (Non-Technical Guide)

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

Think of Story Weaver not as an automated chatbot, but as your **tireless AI co-author, continuity editor, and worldbuilding archivist**.

* **It Remembers Everything**: Before writing each scene, Story Weaver studies your entire book manuscript, your plot summary, your characters' current physical locations, and your world rules.
* **You Remain the Director**: You have complete creative authority. Edit the manuscript directly, rewrite scenes with plain-English feedback, or manually update character sheets whenever inspiration strikes.
* **Never Lose Work**: Every turn is saved atomically. If you don't like where a scene went, one click of **Undo** reverts both your story prose and your background lore files to their exact previous state.
* **Total Freedom**: Write on your personal laptop completely offline using free local models (via Ollama or LM Studio), or connect frontier models like Claude 3.5 Sonnet, Gemini 2.0 Flash, or GPT-4o.

---

### Core Writing Features at a Glance

| Feature | What It Delivers | How to Use It |
| :--- | :--- | :--- |
| **Photographic Memory** | Continuity across hundreds of pages. Characters never forget their pasts or swap eye colors. | Automatic on every turn. |
| **Regenerate with Feedback** | Direct the AI to revise a scene without deleting your chapter or starting over. | Click **Regenerate with feedback** on the latest turn. |
| **Story Bible Sidebar** | Instant visual access to your character dossiers, inventory, timeline, and lore. | Click **Story Files** in the navigation bar. |
| **Voice Dictation** | Speak your brainstorms or narrate dialogue; the AI turns spoken notes into prose. | Click the **Microphone** icon beside the prompt box. |
| **Full-Story Undo / Redo** | Reverses the last turn across the story text, character sheets, and incident logs. | Click **Undo** beneath the latest AI response. |
| **Sectioned Editor** | Fast, lag-free text editing even on 200,000-word manuscripts. | Open any file in the **Story Files** tab. |
| **Background Lore Sweeper** | The AI automatically updates inventory, character injuries, and timeline in the background. | Automatic, or manually trigger via **Run Analysis**. |

---

### The Story Bible at a Glance

Every story you create in Story Weaver contains a dedicated set of interconnected reference documents:

* 📖 **`story.md`**: The continuous, polished manuscript of your book.
* 👤 **`characters.md`**: Detailed profiles for every protagonist, ally, and secondary figure.
* 📍 **`positions.md`**: Where each character is located **right now** in the scene.
* 🏰 **`locations.md`**: Sensory descriptions of cities, taverns, dungeons, and landscapes.
* 🗡️ **`items.md`**: Crucial inventory, weapons, keys, documents, and who holds them.
* 🦹 **`villains.md`**: Antagonists, secret agendas, factions, and threat levels.
* 📜 **`incidents.md`**: A chronological record of historical story events that actually occurred.
* ⏳ **`time.md`**: The narrative clock (day of the week, hour, season, weather).
* 🖋️ **`style.md`**: Your authorial guidelines (tone, point of view, forbidden clichés).
* 📝 **`summary.md`**: A rolling synopsis summarizing everything that has happened so far.
* 🎵 **`audio_log.md`**: Notes on songs, ambient music, or spoken voice memos shared during writing.
* 🔍 **`consistency.md`**: An automated continuity auditor that highlights potential plot holes for your eyes only.

---

### How "Regenerate with Feedback" Works

In other AI tools, if a generated scene misses the mark, you have to delete it and re-type your prompt, or argue with the chatbot.

In Story Weaver:
1. Click **Regenerate with feedback** on the latest turn.
2. Type your creative instructions in the text box:
   > *"Everything was great, but keep Marcus silent during the argument. Emphasize the sound of rain outside, and end with a cliffhanger when the door opens."*
3. Click **Submit**.
4. Story Weaver rolls back the story and reference files to the snapshot before that turn, combines your feedback with the previous draft as a reference guide, and generates an improved revision.
5. The meta-critique and temporary draft are excluded from your final book manuscript.

---

### Speaking Your Story (Voice Dictation & Audio Logs)

1. Click the **Microphone** button next to the prompt area.
2. Speak your instructions, dictate character dialogue, or upload an audio file (up to 25 MB in MP3, WAV, or M4A format).
3. The built-in **3-Stage Media Pipeline** transcribes your audio with zero story bias, captures any song or musical references into `audio_log.md`, and feeds the parsed instructions to the writer model to author the scene.

---

### Background Lore Analysis & Story Repair

Story Weaver features an intelligent background daemon that audits your narrative:
* **Automatic Mode**: Runs quietly after each generated turn, extracting newly introduced characters, injuries, inventory pickups, and plot points.
* **Whole-Story Repair Mode (`turns=0`)**: If you import an existing book from another program or manually edit several chapters, click **Run Analysis** and choose **Whole Story**. The AI reads your complete novel and reconstructs your character dossiers, timeline, and incident logs from scratch.

---

### Step-by-Step: Writing Your First Chapter

1. **Open the App**: Launch Story Weaver and open `http://127.0.0.1:8000` in your browser.
2. **Create a Story**: Click **New Story**, enter a title (e.g., *"The Iron Alchemist"*), and provide an opening premise.
3. **Choose Your Engine**: Select your preferred AI model from the model selector (or configure your API keys in ⚙️ **Settings**).
4. **Author Your First Beat**: In the prompt box, give the AI your starting direction:
   > *"Begin Chapter 1 in the rainy alley outside the Grand Archive. Corvus is waiting for his informant, who is twenty minutes late."*
5. **Review & Expand**: Watch the scene stream into your manuscript. Inspect the **Story Files** sidebar to watch your characters and timeline update in real time!

---

## 3. ⌨️ Keyboard Shortcuts Cheat Sheet

Inside the **Story Files Editor**, Story Weaver provides native desktop shortcuts:

| Key Combination | Action | Detailed Description |
| :--- | :--- | :--- |
| `Ctrl + S` | **Save File** | Atomically commits all changes to disk and PostgreSQL. |
| `Ctrl + A` | **Select Entire File** | Selects the **whole multi-million character document**, spanning all sections. |
| `Ctrl + Z` | **Undo Text Edit** | Reverses the last text modification (groups contiguous keystrokes). |
| `Ctrl + Y` / `Ctrl + Shift + Z` | **Redo Text Edit** | Re-applies the previously undone edit. |
| `Ctrl + F` | **Find & Replace** | Opens search toolbar. Searches wrap across section boundaries. |
| `Alt + Page Down` | **Next Section** | Shifts viewport to the next 24,000-character window. |
| `Alt + Page Up` | **Previous Section** | Shifts viewport to the preceding 24,000-character window. |
| `Ctrl + Home` | **Beginning of Document** | Moves focus and cursor to the absolute start of the file. |
| `Ctrl + End` | **End of Document** | Moves focus and cursor to the absolute end of the file. |
| `Enter` (inside Find/Line) | **Execute Search / Jump** | Finds next match or jumps to the specified line number. |


---

## 4. 📚 The Story Bible Specification (File-by-File Reference)

Story Weaver structures each narrative using 14 modular files. Below is the technical specification and example template for every file in the Story Bible.

### 1. `story.md` (The Master Manuscript)
The continuous, chronological prose of your novel. The AI appends new scenes directly to this document.
```markdown
# Chapter 1: Rain on the Docks

The salt spray from the harbor carried the stench of decaying kelp and coal smoke.
Detective Vance pulled his woolen collar higher against the mist, his boots crunching
against wet gravel...
```

### 2. `characters.md` (Character Dossiers & Relations)
Comprehensive character profiles, physical traits, personality flaws, and relationship dynamics.
```markdown
# CHARACTERS

## Detective Vance Sterling
- **Role**: Protagonist / Lead Investigator
- **Appearance**: Tall, haggard, early 40s. Prematurely gray temples, piercing slate-gray eyes. Wears a battered brown trench coat.
- **Personality**: Cynical, observant, fiercely loyal to old debts. Struggling with a past opiate dependency.
- **Current Status**: Exhausted; investigating the airship disappearance.

## Inspector Alistair Cross
- **Role**: Scotland Yard Liaison / Reluctant Ally
- **Appearance**: Broad-shouldered, immaculate navy uniform, gold pocket watch.
- **Relationship with Vance**: Former partners; tense professional respect tinged with unresolved guilt from the 1892 dock fire.
```

### 3. `positions.md` (Current Physical Locations)
> [!IMPORTANT]
> In the context assembly engine, `positions.md` takes precedence over past narrative text. This guarantees characters never teleport across cities between scenes.
```markdown
# CURRENT POSITIONS (Active Scene: Chapter 3, Scene 2)

- **Detective Vance**: Inside the ruined warehouse on Pier 9, crouching behind crate #402.
- **Inspector Cross**: Waiting outside Pier 9 in the police carriage, observing the street.
- **Lady Elizabeth**: In transit aboard the midnight locomotive toward Dover.
```

### 4. `locations.md` (World Atlas & Spatial Settings)
Detailed geographic, architectural, and environmental descriptions.
```markdown
# LOCATIONS

## Pier 9 (The Lower Embankment)
- **Atmosphere**: Abandoned whaling pier shrouded in river fog. Rotting timber beams, rusted cranes.
- **Key Features**: Warehouse #4 has a collapsed skylight; hidden trapdoor beneath the foreman's desk leads to smuggler conduits.
- **Lighting**: Dim gaslamps along the main promenade; pitch black beneath the loading docks.
```

### 5. `items.md` (Inventory & Artifact Tracking)
Crucial objects, weapons, documents, and who currently possesses them.
```markdown
# KEY ITEMS & INVENTORY

## The Obsidian Key
- **Description**: Heavy black cylinder engraved with cuneiform sigils. Cold to the touch.
- **Current Bearer**: Detective Vance (concealed in his inner coat pocket).
- **Origin**: Recovered from the floating debris of the airship *Aethelgard*.

## Standard Issue Webley .455 Revolver
- **Current Bearer**: Inspector Cross (holstered, 6 rounds loaded).
```

### 6. `villains.md` (Antagonists & Factions)
Antagonist dossiers, secret agendas, resources, and escalating threat tiers.
```markdown
# ANTAGONISTS & FACTIONS

## The Obsidian Syndicate
- **Leader**: "The Architect" (identity unknown; communicates via wax-sealed cipher dispatches).
- **Objective**: Synthesize alchemical gas to paralyze the Ministry of Defense.
- **Active Enforcers**: Silas Grimm (a cybernetically augmented dock brute).
```

### 7. `incidents.md` (Canonical Event Ledger)
Chronological record of established, irrevocable story events that have transpired.
```markdown
# INCIDENT LOG

1. **[1894-10-12 21:00]**: The luxury airship *Aethelgard* vanishes from radar over the Thames Estuary.
2. **[1894-10-12 22:30]**: Vance discovers the wreckage of lifeboat #3 washed up on Pier 9.
3. **[1894-10-12 23:15]**: Vance is ambushed by Silas Grimm; Vance shoots Grimm in the shoulder before escaping.
```

### 8. `time.md` (Timeline & Chronology)
Tracks in-universe date, time of day, season, and elapsed narrative duration.
```markdown
# STORY TIMELINE

- **Current In-Universe Date**: October 13, 1894
- **Current Time**: 01:45 AM (Night)
- **Elapsed Story Time**: 4 hours and 45 minutes since the case began
- **Weather Condition**: Torrential rain with heavy coastal fog
```

### 9. `style.md` (Authorial Voice & Pacing)
Tone, prose cadence, vocabulary boundaries, and perspective rules.
```markdown
# STYLE GUIDE

- **Perspective**: Third-Person Limited (strictly anchored to Detective Vance).
- **Tone**: Gritty Victorian noir, atmospheric, introspective, visceral.
- **Sensory Details**: Emphasize smells (sulfur, rain, wet wool), cold dampness, and auditory cues.
- **Constraints**: Avoid modern idioms, anachronistic slang, and overly poetic flowery adjectives. Keep dialogue clipped and authentic.
```

### 10. `summary.md` (Rolling Plot Synopsis)
Concise chapter-by-chapter recap maintained by the background analysis engine.
```markdown
# ROLLING SUMMARY

- **Prologue**: The *Aethelgard* departs Paris carrying dignitaries before disappearing in fog.
- **Chapter 1**: Vance is summoned by Scotland Yard to investigate wreckage on Pier 9.
- **Chapter 2**: Vance interrogates a terrified dockworker and uncovers an Obsidian Syndicate emblem.
```

### 11. `rules.md` (Hard Narrative Constraints)
System-level storytelling guardrails and formatting mandates.
```markdown
# HARD RULES

1. Never break character perspective or reveal information Vance does not know.
2. Do not resolve the mystery of the Obsidian Key prematurely.
3. End each generation turn on an active narrative beat or dramatic choice.
4. Format all dialogue with standard quotation marks.
```

### 12. `consistency.md` (Automated Diagnostic Audit)
Diagnostic warnings generated for author verification.
> [!NOTE]
> `consistency.md` is strictly excluded from LLM generation prompts (`SKIP_FILES`) to prevent diagnostic feedback loops.
```markdown
# CONTINUITY AUDIT DIAGNOSTICS (Generated 02:15 UTC)

- [PASSED] Character Inventory: Vance still possesses the Obsidian Key.
- [WARNING - Line 450]: Inspector Cross mentions his pocket watch is broken, but checked the time on Line 312.
- [PASSED] Spatial Consistency: Corvus remained at Pier 9 throughout Chapter 2.
```

### 13. `audio_log.md` (Acoustic & Musical Memory)
Captures transcribed voice memos, user-uploaded audio metadata, and song inspirations.
```markdown
# AUDIO LOG

- **Recording #1 (2026-09-10 14:20)**: User narrated scene concept: *"Vance hears a music box playing inside the empty warehouse..."*
- **Song Track Attached**: Chopin's Nocturne in C Minor (used as motif for the antagonist's calling card).
```

### 14. `chat_log.json` (Structured Turn History)
Machine-readable array of all prompt and response turns, including captured reasoning tags.
```json
[
  {
    "role": "user",
    "text": "Vance enters the warehouse through the shattered window.",
    "time": "1894-10-13 01:50:00"
  },
  {
    "role": "ai",
    "text": "Glass crunched beneath the leather of Vance's heel as he swung his legs over the splintered sill...",
    "model": "gemini-2.0-flash",
    "model_thoughts": "<thought>Establish claustrophobic tension. Emphasize smell of ozone.</thought>",
    "time": "1894-10-13 01:50:12"
  }
]
```


---

## 5. ⚡ Quick Start Guide

### Method 1: Windows One-Click Batch Script

1. Clone or download this repository to your PC.
2. Double-click **`Start_Story_Weaver.bat`**.
   - Kills any orphan background instances to avoid port conflicts.
   - Activates or creates the `.venv` virtual environment.
   - Launches the FastAPI backend on port `8000`.
3. Open **`http://127.0.0.1:8000`** in your browser.

---

### Method 2: Cross-Platform Terminal (macOS, Linux, Windows)

```bash
# 1. Clone the repository
git clone https://github.com/surajpaswan123/story-weaver.git
cd story-weaver

# 2. Set up Python environment
python -m venv .venv
source .venv/bin/activate  # On Windows PowerShell: .\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run application
python main.py
```

---

### Method 3: Local Super-Admin Desktop Mode (Zero Cloud)

To run Story Weaver completely offline without configuring Firebase Authentication or external databases:

Create a `.env` file in the project root:
```env
ALLOW_LOCAL_SUPER_ADMIN=true
ALLOW_UNVERIFIED_JWT=true
PORT=8000
HOST=127.0.0.1
```

* **Zero Authentication**: Automatically logs in as local super-admin.
* **Disk-Based Storage**: All stories and files save directly to `./stories/local_admin/`.

---

## 6. 🔬 Anatomy of a Story Turn (Microsecond Lifecycle Trace)

When you click **Generate Story** or **Submit Feedback**, here is the exact trace executed by Story Weaver:

```
[User clicks "Send" in Browser SPA]
  │
  ├─ 1. POST /generate (FastAPI)
  │     └─ Verifies JWT / Super-Admin credentials (require_authenticated_user)
  │     └─ Enforces API key presence (User Settings or system default)
  │
  ├─ 2. TurnProgress Lock Acquisition (runtime_support.py)
  │     └─ Obtains thread-safe lock: threading.RLock(uid, story_id)
  │     └─ Registers state: 'starting', generates unique run_id token
  │
  ├─ 3. Context Pipeline Assembly (main.py)
  │     └─ Loads Story Bible files from disk/PostgreSQL
  │     └─ Filters out SKIP_FILES: rules.md, consistency.md, story.md
  │     └─ Packs priority order: Rules -> Lore -> World -> Positions -> Summary
  │     └─ Appends full manuscript (story.md) immediately before prompt for recency
  │
  ├─ 4. Protocol Translation & Gateway Dispatch (openai_compat.py)
  │     └─ Detects provider: Anthropic Messages, OpenAI Responses, or Google GenAI
  │     └─ Formats messages, system prompts, and reasoning effort parameters
  │
  ├─ 5. Streaming Generator & Heartbeat Loop (relay_stream)
  │     └─ Spawns daemon background thread to execute model call
  │     └─ Pushes text chunks into bounded queue (maxsize=100)
  │     └─ Emits SSE stream to client with 15-second keepalive pings (: ping\n\n)
  │     └─ Updates TurnProgress state: 'generating'
  │
  ├─ 6. Client Disconnect Protection
  │     └─ If browser tab closes, consumer terminates, but worker CONTINUES
  │
  ├─ 7. Completion & Atomic Transactional Commit
  │     └─ Appends completed AI response to story.md and chat_log.json
  │     └─ Opens single SQL transaction: BEGIN ... COMMIT in PostgreSQL
  │     └─ Writes all updated files in one atomic batch
  │     └─ Updates TurnProgress state: 'completed'
  │
  └─ 8. Asynchronous Background Lore Sweep
        └─ Triggers background task: POST /analyze/{story_id}?turns=1
        └─ Secondary model extracts updated inventory, positions, and character health
        └─ Atomically updates items.md, positions.md, and summary.md
```


---

## 7. 🧠 Technical Architecture & Engineering Deep-Dive

### High-Level Architecture Diagram

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
        MediaPipeline["3-Stage Audio Processing Pipeline"]
        LivenessProbe["/ping Liveness Probe (Zero I/O, <5ms)"]
        LogBuffer["Circular In-Memory Log Interceptor (500 lines)"]
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
    Router --> MediaPipeline
    MediaPipeline --> RouterHub
    TurnMgr -->|Atomic Multi-File Commit| PG
    PG -.->|Initial Import Fallback| FSFallback
    TurnMgr -->|Local Sync| DiskCache
    Router --> HistoryPaginator
    HistoryPaginator --> PG
    Router --> LogBuffer
```

---

### Multi-Provider Protocol Unification (`openai_compat.py`)

Different model providers utilize fundamentally incompatible network formats. Story Weaver unifies these protocols inside [`openai_compat.py`](file:///C:/Users/suraj/story-weaver-repo/openai_compat.py):

* **Responses API Client**: Implements the OpenAI Responses format (`/responses`), passing `input` and `reasoning.effort` (`none`, `minimal`, `low`, `medium`, `high`, `xhigh`). It inspects the `output` array, verifies status != `"incomplete"`, and extracts `output_text` parts while stripping non-prose items.
* **Messages API Client**: Implements the Anthropic Messages format (`/messages`), passing `anthropic-version: 2023-06-01`, a top-level `system` prompt, and user/assistant turns. Supports custom token ceilings up to 131,072.
* **OpenCode Zen Router**: Automatically routes by model family (`muse-spark-*` $ightarrow$ Responses; `claude-*` $ightarrow$ Messages; `deepseek-*` $ightarrow$ Chat Completions).

---

### Token Attention Ordering & Reciprocal Recency

Transformer attention heads experience recency bias: tokens situated closer to the generation prompt receive higher attention weights than tokens positioned at the beginning of the context window.

Story Weaver structures prompt assembly intentionally:
```
[1. Rules & Constraints (rules.md)]
[2. Character Dossiers (characters.md)]
[3. Immediate Positions (positions.md)]  <-- Priority over historical mentions
[4. Locations & Items (locations.md, items.md)]
[5. Canonical Event Ledger (incidents.md)]
[6. Narrative Timeline & Summary (time.md, summary.md)]
[7. Master Manuscript (story.md)]       <-- Closest to generation point
[8. Current Prompt / Revision Feedback]
```
This guarantees that prose rhythm, dialogue style, and immediate character actions are governed by the most recent manuscript pages rather than static background lore.

---

### The 3-Stage Media Pipeline (Audio Processing)

When generating narrative from audio recordings (`POST /generate-audio`):
1. **Stage 1 (Media Analyzer)**: An audio-capable model (`input-audio-model`) evaluates the uploaded audio file (up to 25 MB). To eliminate hallucinations, this stage receives **zero story context** and focuses exclusively on high-fidelity speech transcription, lyric extraction, vocal mood, and acoustic cues.
2. **Stage 2 (Story Generator)**: The primary writer model (`input-story-model`) ingests the parsed audio breakdown alongside the complete Story Bible context to write the narrative continuation.
3. **Stage 3 (Rules & Style Editor)**: A rules refinement model checks the generated prose against `rules.md` and `style.md` to ensure structural and tonal compliance.

---

### Diagnostic Isolation Architecture

Automated diagnostics (such as timeline audits and inventory checks) must never bleed into fiction prose. Story Weaver enforces strict diagnostic isolation:
```python
SKIP_FILES = {"rules.md", "context.md", "story.md", "consistency.md"}
```
`consistency.md` is populated by background diagnostic jobs for author verification, but is completely excluded from LLM generation context, preventing hallucinated meta-dialogue.

---

### Streaming, Concurrency & Disconnect Survivability

Unlike conventional web applications where closing a browser tab triggers an immediate task cancellation that corrupts in-flight files, Story Weaver implements **Asynchronous Disconnect Survivability**:
1. **Thread-Safe Story Locks**: Managed via `TurnProgress` using `threading.RLock()` keyed by `(uid, story_id)`.
2. **Decoupled Worker Queue**: A worker thread feeds text chunks to a bounded `queue.Queue(maxsize=100)`. If the client disconnects, the SSE stream terminates, but the background worker completes its execution and safely commits the turn to PostgreSQL.
3. **Turn Status Polling (`/story/{id}/generation-status`)**: Clients poll status records to resume watching active generations after page reloads.

---

### Virtual Sectioned File Viewport (24k Char Windows)

To prevent DOM reflow stalls when editing multi-hundred-thousand-word books, [`static/file-editor.js`](file:///C:/Users/suraj/story-weaver-repo/static/file-editor.js) renders the file through a virtualized sectioned viewport:
* **24,000-Character Threshold**: Files exceeding 24k characters are segmented into navigable windows.
* **Unicode Astral Plane & CRLF Boundary Safeguard**:
  ```javascript
  function boundary(text, offset) {
      offset = Math.max(0, Math.min(text.length, offset));
      const code = text.charCodeAt(offset);
      if ((code >= 0xDC00 && code <= 0xDFFF) ||
          (text[offset] === '\n' && text[offset - 1] === '\r')) offset--;
      return Math.max(0, offset);
  }
  ```
  Surrogate pairs (emojis) and Windows CRLF newlines are never bisected across viewports.
* **Whole-File Atomic Operations**: Global shortcuts (`Ctrl + A`, `Ctrl + S`, Copy All, Find & Replace) operate seamlessly on the entire document across all sections.
* **Bounded Differential Undo Stack**: Keeps character diffs up to 500 operations within a 20 MiB memory budget.

---

### Chat History JSON Schema & Validation Engine

Authors can open and modify `chat_log.json` directly in Story Files:
* **Validation Rules**:
  - Each element must be a JSON object with `role` (`"user"` or `"ai"`) and string `text`.
  - Optional fields: `model` (string), `time` (string), `model_thoughts` (string).
* **Syntax Error Guard**: Malformed JSON displays line and column numbers in real time, preventing corrupt writes.

---

### Incremental JSON History Streaming (`ijson`)

To prevent Out-Of-Memory (OOM) crashes on small cloud instances (e.g., 0.5 vCPU / 1 GB RAM):
* `GET /story/{story_id}/chat` utilizes [`ijson`](https://github.com/ICRAR/ijson) to parse large transcripts iteratively.
* Returns paged slices (default 40 messages) with a 256KB soft budget.
* Optimistic revision tokens prevent conflicting writes (returns HTTP `409 Conflict` if history shifted).

---

### Live Server Log Interceptor & Slide-Out Panel

Story Weaver captures standard output and standard error using a custom stream interceptor:
* **Circular Buffer**: Retains the latest 500 lines in a thread-safe `collections.deque(maxlen=500)`.
* **Truncation Safeguard**: Lines exceeding 4,096 characters are truncated to protect memory.
* **UI Diagnostic Slide-Out**: View live logs directly inside the web interface via `GET /api/logs`.

---

### Accessibility (a11y) & Screen-Reader Architecture

Story Weaver is built in compliance with **WCAG 2.1 AA** standards:
* **Semantic Native Controls**: Buttons and inputs use semantic HTML rather than unclickable `<div>` elements.
* **ARIA Live Regions**: Screen readers receive dynamic announcements when generation states change, files save, or clipboard actions succeed.
* **Focus Management**: Opening modals (Settings, Feedback, File Editor) automatically traps and restores focus.


---

## 8. 💾 Storage Engine & SQL Architecture

### Relational Schema (PostgreSQL / Neon)

Story Weaver uses PostgreSQL as its primary ACID storage layer. On startup, the server automatically provisions the required relational tables:

```sql
-- User API Keys and Provider Configurations
CREATE TABLE IF NOT EXISTS user_keys (
    uid VARCHAR(255) PRIMARY KEY,
    keys JSONB NOT NULL,
    updated_at DOUBLE PRECISION DEFAULT 0
);

-- Master Story Documents and Reference Files
CREATE TABLE IF NOT EXISTS user_stories (
    uid VARCHAR(255) NOT NULL,
    story_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL,
    title VARCHAR(255),
    PRIMARY KEY (uid, story_id, file_name)
);

-- Recommended Index for High-Performance File Listing
CREATE INDEX IF NOT EXISTS idx_user_stories_lookup 
ON user_stories (uid, story_id);
```

---

### Single-Transaction Atomic Multi-File Commits

At the conclusion of each generation turn, multiple files are modified simultaneously:
* `story.md` (appended prose)
* `chat_log.json` (new turns and thoughts)
* `incidents.md` (new events)
* `positions.md` (updated locations)
* `summary.md` (updated rolling recap)

Story Weaver writes these updates inside a **single SQL transaction**:
```python
conn = psycopg2.connect(db_conn_str)
with conn.cursor() as cur:
    for file_name, content in modified_files.items():
        cur.execute("""
            INSERT INTO user_stories (uid, story_id, file_name, content, updated_at, title)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (uid, story_id, file_name)
            DO UPDATE SET content = EXCLUDED.content, updated_at = EXCLUDED.updated_at;
        """, (uid, story_id, file_name, content, time.time(), title))
conn.commit()  # All files committed atomically
```
If a database disconnect occurs mid-save, the entire transaction rolls back cleanly, preventing partial manuscript corruption.

---

### Zero-Loss Legacy Firestore Migration

For existing instances migrating from Cloud Firestore:
1. When opening a story, Story Weaver queries PostgreSQL first.
2. If PostgreSQL has no rows for that story, it inspects Firestore.
3. If Firestore documents are present, it imports them into PostgreSQL and caches them locally.
4. Subsequent reads and writes execute exclusively against PostgreSQL.

---

### Local Caching Layer (`/stories/{uid}/{story_id}`)

To ensure sub-millisecond file reads, stories are cached locally on disk:
```
stories/
└── usr_98a72b1c/
    └── sty_44f10a8e/
        ├── story.md
        ├── chat_log.json
        ├── characters.md
        ├── positions.md
        ├── locations.md
        ├── items.md
        ├── villains.md
        ├── incidents.md
        ├── time.md
        ├── style.md
        ├── summary.md
        ├── rules.md
        ├── consistency.md
        └── audio_log.md
```

---

### Database Backup & Disaster Recovery Commands

```bash
# Export full database backup (schema + data)
pg_dump "postgresql://user:password@host/neondb?sslmode=require" -F c -b -v -f story_weaver_backup.dump

# Restore database backup to a new instance
pg_restore -d "postgresql://user:password@new-host/neondb?sslmode=require" -v story_weaver_backup.dump
```


---

## 9. 🔌 Local Models & Provider Cookbook

### 1. Connecting Local Models (Ollama, LM Studio, vLLM)

Run 100% private, free, uncensored models on your own GPU:

#### Step A: Configure Local CORS
Local AI servers must accept requests from the browser:

* **Ollama (Windows)**:
  1. Close Ollama from the system tray.
  2. Open PowerShell as Administrator and run:
     ```powershell
     [System.Environment]::SetEnvironmentVariable('OLLAMA_ORIGINS', '*', 'User')
     ```
  3. Restart Ollama.
* **Ollama (macOS / Linux)**:
  ```bash
  OLLAMA_ORIGINS="*" ollama serve
  ```
* **LM Studio**:
  1. Navigate to the **Local Server** tab (`<->`).
  2. Toggle **Enable CORS** to ON.
  3. Start the server on port `1234`.

#### Step B: Connect in Story Weaver
1. In Story Weaver, select **Local OpenAI-Compatible Server**.
2. Set Server URL:
   - Ollama: `http://localhost:11434/v1`
   - LM Studio: `http://localhost:1234/v1`
3. Enter your model name (e.g., `llama3.3`, `mistral-nemo`, `qwen2.5:14b`).
4. **Zero-Hop Architecture**: The browser communicates directly with your localhost port. Zero data is sent to external cloud servers.

---

### 2. Anthropic Messages API (Direct & Gateway)

* **Direct URL**: `https://api.anthropic.com/v1/messages`
* **Custom Gateway**: `https://your-proxy.com/v1/messages`
* **Configuration**:
  - API Key: `sk-ant-...`
  - Max Output Tokens: Up to `131,072` (or leave empty for provider default).
  - Automatically captures model thinking tags into `chat_log.json`.

---

### 3. Google Gemini (Native `google-genai` SDK)

* **Configuration**: Enter your Google AI Studio API Key (`AIzaSy...`).
* **Supported Models**: `gemini-2.0-flash`, `gemini-2.5-pro`, `gemini-2.0-flash-lite`, `gemini-1.5-pro`.
* **Multimodal Audio**: Native support for transcribing and writing from voice dictation.

---

### 4. OpenCode Zen Dynamic Protocol Routing

* **Base URL**: `https://opencode.ai/zen/v1`
* **Automatic Routing Matrix**:
  - `muse-spark-*`, `gpt-*`, `grok-*` $ightarrow$ Responses API (`reasoning.effort` supported)
  - `claude-*`, `qwen*` $ightarrow$ Anthropic Messages API
  - `deepseek-*`, `mimo-*`, `glm-*`, `minimax-*` $ightarrow$ Chat Completions API

---

### 5. OpenAI Chat Completions & Responses Protocols

* **Base URL**: `https://api.openai.com/v1`
* **Chat Completions**: Standard `/chat/completions` for `gpt-4o`, `gpt-4o-mini`.
* **Responses API**: Uses `/responses` for `o1`, `o3-mini`, allowing explicit reasoning effort selection (`low`, `medium`, `high`, `xhigh`).

---

### 6. Groq, NVIDIA NIM, and OpenRouter

* **Groq**: Ultra-fast Llama 3.3 (70B) streaming at 300+ tokens/second.
* **NVIDIA NIM**: Direct access to DeepSeek-V3 and Llama 3.1 405B via `nvapi-...`.
* **OpenRouter**: Unified access to over 200 models using `sk-or-...`.

---

### 7. Rate-Limit Resilience & 429 Exponential Backoff

When providers trigger rate-limit cooldowns:
* Story Weaver preserves the HTTP `429` status code.
* The frontend displays an active cooldown countdown badge.
* Uncommitted prompts and feedback instructions remain cached, allowing users to click **Retry** once the cooldown expires.

---

### 8. Multi-Key Rotation & Key Masking

* **Key Masking**: Stored keys are masked on the client (`sk-...a8F2`).
* **Automatic Failover**: If a key hits rate limits, the backend rotates to the next configured key automatically.


---

## 10. 🚀 Deployment & Hosting Playbooks

### Playbook A: Docker & Docker Compose

#### `docker-compose.yml`
```yaml
services:
  story-weaver:
    image: ghcr.io/surajpaswan123/story-weaver:main
    container_name: story-weaver
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - HOST=0.0.0.0
      - PORT=8000
      - DATABASE_URL=postgresql://user:password@postgres:5432/storyweaver
      - ALLOW_LOCAL_SUPER_ADMIN=true
    volumes:
      - story_data:/app/stories
    depends_on:
      - postgres

  postgres:
    image: postgres:16-alpine
    container_name: story-weaver-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=storyweaver
    volumes:
      - pg_data:/var/lib/postgresql/data

volumes:
  story_data:
  pg_data:
```

Launch with:
```bash
docker compose up -d
```

---

### Playbook B: ClawCloud Run Deployment

Refer to [`docs/clawcloud.md`](file:///C:/Users/suraj/story-weaver-repo/docs/clawcloud.md) for full ClawCloud configuration:
1. **Container Image**: `ghcr.io/surajpaswan123/story-weaver:main`
2. **Sizing**: 0.5 vCPU, 1 GB RAM (Fixed 1 instance).
3. **Container Port**: `8000` (HTTP).
4. **Health Probe**: `GET /ping` on port 8000.
5. **Environment Variables**: Set `DATABASE_URL` and `FIREBASE_SERVICE_ACCOUNT_JSON`.

---

### Playbook C: Render Web Service + 24/7 cron-job.org Ping

1. Deploy as a Web Service on Render connecting your GitHub repository.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `python main.py`
4. Configure Keep-Alive on [cron-job.org](https://cron-job.org/):
   - **URL**: `https://your-service.onrender.com/ping`
   - **Method**: `GET`
   - **Interval**: Every 10 minutes
   - **Result**: Returns HTTP 200 `OK` (2 bytes). Prevents free-tier container sleep.

---

### Playbook D: Linux Production Deployment with `systemd`

Create `/etc/systemd/system/story-weaver.service`:
```ini
[Unit]
Description=Story Weaver Production Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/story-weaver
ExecStart=/var/www/story-weaver/.venv/bin/python main.py
Restart=always
RestartSec=5
Environment=HOST=127.0.0.1
Environment=PORT=8000
Environment=DATABASE_URL=postgresql://user:pass@localhost:5432/storyweaver

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable story-weaver
sudo systemctl start story-weaver
```

---

### Playbook E: Windows Auto-Start via Task Scheduler

1. Open **Task Scheduler** in Windows.
2. Click **Create Basic Task** -> Name: `Story Weaver AutoStart`.
3. Trigger: **When I log on**.
4. Action: **Start a program**.
5. Program/script: `C:\Users\suraj\story-weaver-repo\Start_Story_Weaver.bat`
6. Finish. Story Weaver will launch automatically when you sign in!


---

## 11. 📡 REST & SSE API Reference

| Method | Endpoint | Auth | Request Body | Description |
| :--- | :--- | :---: | :--- | :--- |
| `GET` | `/ping` | None | None | Liveness check for keepalive pingers. Returns 200 `OK`. |
| `GET` | `/stories` | User | None | Lists all stories owned by authenticated user. |
| `POST` | `/stories/create` | User | `{"title": str, "premise": str}` | Creates a new story and initializes Story Bible files. |
| `DELETE` | `/story/{story_id}` | User | None | Deletes story, SQL records, and local disk cache. |
| `GET` | `/story/{story_id}` | User | None | Fetches story metadata, file list, and turn count. |
| `GET` | `/story/{story_id}/full` | User | None | Returns the complete manuscript (`story.md`). |
| `GET` | `/story/{story_id}/chat` | User | Query: `last=40`, `revision` | Fetches paged chat history using streaming `ijson`. |
| `GET` | `/story/{story_id}/generation-status` | User | None | Returns live generation progress state (`generating`, `finalizing`, etc.). |
| `POST` | `/generate` | User | `StoryInput` (story_id, prompt, etc.) | Dispatches background worker and streams SSE chunks. |
| `POST` | `/story/{story_id}/stop` | User | None | Cancels active generation turn for this story. |
| `POST` | `/story/{story_id}/undo` | User | None | Atomic rollback of story prose, reference files, and history. |
| `POST` | `/story/{story_id}/retry` | User | None | Retries the last failed generation turn. |
| `POST` | `/generate-audio` | User | Form multipart (audio file, prompt) | Executes 3-stage media analysis and story generation. |
| `POST` | `/analyze/{story_id}` | User | Query: `turns=0` (whole story) | Runs background character and lore extraction sweep. |
| `GET` | `/analyze/{story_id}/status` | User | None | Checks background lore analysis state. |
| `POST` | `/story/{story_id}/cancel-analysis` | User | None | Terminates active background lore analysis. |
| `GET` | `/story/{story_id}/files` | User | None | Lists all markdown files in the Story Bible. |
| `GET` | `/story/{story_id}/file/{filename}` | User | None | Fetches raw content of a specific Story Bible file. |
| `PUT` | `/story/{story_id}/file/{filename}` | User | `{"content": str}` | Saves edited content of a Story Bible file. |
| `DELETE` | `/story/{story_id}/file/{filename}` | User | None | Deletes a custom reference file. |
| `GET` | `/api/providers-models` | User | None | Live catalog discovery across configured AI providers. |
| `GET` | `/api/user/settings` | User | None | Returns user configuration and masked API keys. |
| `POST` | `/api/user/settings` | User | `{"keys": {...}, "models": {...}}` | Updates API keys, custom URLs, and pipeline models. |
| `GET` | `/api/logs` | User | None | Returns recent in-memory server log buffer (500 lines). |


---

## 12. ⚠️ Complete HTTP Error & Troubleshooting Dictionary

| HTTP Code | Error Message | Root Cause | Exact Resolution |
| :---: | :--- | :--- | :--- |
| `200` | `OK` | Successful operation. | Normal operation. |
| `400` | `Story is empty, nothing to analyze` | Triggered analysis on a blank story. | Generate at least one turn before running analysis. |
| `401` | `Authentication Required` | Missing or invalid Firebase JWT token. | Sign in with Google or enable `ALLOW_LOCAL_SUPER_ADMIN=true`. |
| `403` | `API Key Required` | Standard user logged in without API keys. | Open ⚙️ **Settings** and add an API key for your chosen provider. |
| `404` | `Story not found` | Invalid `story_id` or story was deleted. | Verify story ID in URL or create a new story. |
| `409` | `Wait for current generation to finish` | Generation or analysis lock is currently held. | Wait for in-flight turn to complete or click **Stop Generation**. |
| `409` | `Revision conflict` (in `/chat`) | Transcript updated while paging history. | Client automatically reloads latest revision. |
| `413` | `Audio file too large (max 25 MB)` | Uploaded audio file exceeds size cap. | Compress audio to MP3 or split into shorter recordings. |
| `415` | `Only audio files are supported` | Non-audio file uploaded to `/generate-audio`. | Upload valid MP3, WAV, M4A, or OGG audio files. |
| `429` | `Rate limit exceeded` | Upstream AI provider quota exhausted. | Wait for countdown cooldown or rotate API keys in Settings. |
| `500` | `No AI providers are configured or reachable` | Misconfigured base URL or unreachable host. | Verify API key and network connectivity in Settings. |

---

## 13. 🧪 Testing & Quality Assurance Suite

Story Weaver features comprehensive unit, integration, and end-to-end frontend tests:

```powershell
# 1. Install development dependencies
pip install -r requirements-dev.txt

# 2. Run backend Python test suite
python -m pytest -q

# 3. Run frontend Node.js integration suite
node --test tests/test_model_discovery_frontend.cjs `
            tests/test_feedback_frontend.cjs `
            tests/test_chat_log_frontend.cjs `
            tests/test_file_editor.cjs
```

---

## 14. ❓ Frequently Asked Questions (FAQ)

<details>
<summary><strong>Q: Can I write uncensored or dark fantasy fiction?</strong></summary>
<br />
Yes! While commercial APIs (OpenAI, Anthropic) enforce vendor safety filters, Story Weaver applies zero censorship. Connect local uncensored models (such as Llama 3, Mistral, or Starcoder) via Ollama or LM Studio for complete narrative freedom.
</details>

<details>
<summary><strong>Q: Are my stories private? Will they be used to train AI models?</strong></summary>
<br />
Your work is completely private. Commercial API calls use enterprise endpoints where training on user inputs is disabled by default. If you use local models (Ollama/LM Studio), your manuscripts and prompts never leave your local physical hardware.
</details>

<details>
<summary><strong>Q: How long can a book get before Story Weaver slows down?</strong></summary>
<br />
Story Weaver has been tested on novels exceeding 250,000 words. Thanks to the 24,000-character sectioned editor, the browser never bogs down, and the backend leverages 1M+ token context windows seamlessly.
</details>

<details>
<summary><strong>Q: What happens if my browser crashes during a generation?</strong></summary>
<br />
Your work is protected! The backend continues generating and saves the completed chapter to PostgreSQL. When you reopen the site, Story Weaver syncs the latest chapter automatically.
</details>

<details>
<summary><strong>Q: How do I export my finished book?</strong></summary>
<br />
Open **Story Files**, select `story.md`, and click **Download file**. You will receive a clean, standard markdown file ready for compilation in Pandoc, Scrivener, or Kindle Direct Publishing.
</details>

---

## 15. 📄 License & Credits

* **Author**: [Suraj Paswan](https://github.com/surajpaswan123)
* **License**: [MIT License](LICENSE). Free for personal, commercial, and educational creative writing.

<p align="center">
  <sub>Crafted with passion for novelists, worldbuilders, and storytellers everywhere.</sub>
</p>
