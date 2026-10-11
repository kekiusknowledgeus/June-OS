# June architecture

June is a Python application rooted in its checkout (currently `D:\June-V0-Test`),
or an explicit `--root`/`JUNE_ROOT`, with its environment in `.venv` and runtime
state in `data`. It is a working prototype, not a finished autonomous OS.

`Runtime` owns orchestration. Interfaces contain no provider-specific orchestration: `JuneBrain` returns `Decision` values; `Registry` advertises tools; `Policy` decides whether the host needs approval; `Store` persists local records; `EventBus` routes observed events. Both desktop and browser interfaces call the same authenticated FastAPI application. The terminal runs the same runtime directly.

Request flow: enqueue → acquire the single execution slot → assemble bounded relevant context → call brain → validate tool arguments → enforce policy → await exact-action approval when needed → execute under timeout → return observations to the brain → repeat until response, cancellation, time limit, repeated action, or step budget. The default is 24 iterations, 8 calls per iteration and 10 minutes per task. A maximum of 8 jobs can be queued.

SQLite WAL stores messages, memories, tasks, projects, schedules, events, notifications, jobs, approvals, working context and timelines. Context fields carry sources, timestamps, confidence and stale flags; transient observations become stale after restart. Only selected projects, relevant memories, bounded working context and recent conversation enter inference. Restart marks unfinished jobs interrupted and expires approvals; it never replays shell or GUI actions. An OS file lock prevents two active runtimes scheduling against the same database.

## Modules

| Module | Responsibility |
|---|---|
| `runtime.py` | Context, agent loop, policy enforcement, jobs and coordination |
| `brain.py` | OpenAI Responses adapter and loopback compatible local model adapter |
| `groq_brain.py` | Groq streaming text/tool transport, connection reuse, cooldowns and complete-response validation |
| `v0_brain.py`, `v0_model.py` | Separate experimental character model; no tool calls or vision |
| `context.py`, `commands.py` | Durable working context, timelines, local commands and continuation briefing |
| `apps.py`, `workflows.py` | Structured project adapters and evidence gates for coding/research |
| `inspection.py`, `hotkey.py`, `startup.py` | Honest runtime inspection, global shortcut and opt-in login startup |
| `store.py`, `memory.py` | Durable state, provenance, deduplication, local semantic search |
| `security.py` | Risk levels, path policy, credential access, redaction |
| `tools.py` | Registry, files, read-only Git, cancellable shell processes |
| `windows.py`, `camera.py` | Observations, screen/camera capture and approved desktop actions |
| `voice.py`, `scripts/` | Local Windows recognition, wake phrase, speech output and interruption |
| `webtools.py` | Separate research and isolated Playwright browser adapters |
| `automation.py` | Durable reminders, scheduled prompts, event dispatch, watchers, notification relevance |
| `integrations.py`, `devices.py` | Email, calendar, GitHub and hardware contracts |
| `api.py`, `desktop.py`, `web/` | Authenticated local API, native Tk/tray and dashboard |

Background work is a five-second timer and a fifteen-second opt-in watcher scan. Closing the native window hides it to the tray; Exit shuts down the runtime. `serve` can run without either UI. Windows login startup is not installed automatically.

## Provider contracts

`JuneBrain` exposes respond, reason, plan, choose_tools, interpret_observation, extract_memory, summarize and analyze_image. Audio transcription belongs to `SpeechProvider`; the base brain reports that explicitly instead of pretending to accept audio. `VisionProvider` aliases the brain contract. `EmbeddingProvider.rank()` and `SearchProvider.search()` are separately replaceable. `Browser` isolates browser state from research fetches.

## Current limits

Groq, OpenAI and a generic local endpoint are available alongside experimental
June V0. No hosted provider was live-tested in the 2026-10-11 pass. External
outages produce waiting_external jobs; narrow local commands continue without
inference. One action lane prevents competing agent actions. Cancellation and
selected local questions bypass that lane. Daily call limits, usage and latency
are local telemetry. Notification/speech failures do not erase completed work.

Local model inference requires a separately configured server. No weights were installed. Hardware contracts do not imply connected hardware. GUI verification requires a recent capture ID, stable target handle/bounds/title/pixels, and analysis of the resulting image before another action. This conservative guard can reject animated pages and changed focus. Model analysis alone is not a formal proof of the outcome.
