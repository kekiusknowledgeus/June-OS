# Validation

## Current development pass — 2026-10-11

Baseline: 110 Python tests passed. The earlier historical results below were
not rerun against live personal apps or accounts in this pass.

Final verification commands:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/browser_bridge.test.cjs
node --check extensions/june-browser-bridge/background.js
node --check june/web/settings.js
.\.venv\Scripts\python.exe -m compileall -q june tests
git diff --check
```

Final result: **146 Python tests passed** (74.75 seconds), **5 Node tests passed**.
Python compilation, extension/settings JavaScript syntax checks and Git whitespace
checks passed. One upstream Starlette/httpx TestClient deprecation warning remains.
Changes are staged on `feature/june-v0-experimental-brain`; committing is pending
the owner's Git author name/email because this checkout has no configured identity.
New tests
cover streamed Groq text/tools, partial-response refusal, cooldowns, tool-history
grouping, mixed capability selection, failed batch handling, bridge claim and
ticket lifecycle, speech deadlines/privacy, routing, preference persistence and
the desktop verification gate. Tests block external sockets, isolate credentials
and use synthetic desktop/browser observations.

Silent Kokoro CPU measurements and remaining attended acceptance checks are in
[the audit](development-audit-2026-10-11.md). No live Groq request, real browser
action or microphone recording was performed.

## Historical validation — 2026-10-03 (not revalidated here)

This phase continued the existing repository. Latest completed full regression run: **107 passed**; one upstream Starlette/httpx TestClient deprecation warning. Python compilation passes. No numerical “80% complete” certification is claimed.

## Deterministic browser routing (2026-10-03)

**Result:** full regression suite 107 passed (one upstream TestClient deprecation warning). All eight real Windows browser-opening requests were accepted with Gemini disabled, zero provider calls and no isolated browser launch. Remote page loads were not verified.

The local router now resolves explicit HTTP(S) URLs and domains before any provider access, preserving paths, case-sensitive URL components, ports, queries and fragments. A small alias table and reviewed local registry resolve common names; unknown names open an encoded Google search instead of guessing a domain. Google and YouTube searches construct URLs locally. Existing app/project commands retain priority over unknown-site fallback.

`tests/test_browser_commands.py` exercises 21 navigation/search cases through a real Runtime job loop with Gemini inference configured to fail and Playwright startup forbidden, plus resolver, malformed-URL, existing-command and privacy/error cases. Every browser job and routing audit records `route=local_browser_command` and `provider_calls=0`. No provider inference/usage records are created.

`scripts/smoke_browser_routing.py --open-browser` runs all eight requested acceptance commands with a disabled provider and zero API-call budget, dispatching to the real Windows default-browser opener. Evidence is in `data/evidence/browser-routing.json`. OS acceptance of a tab-opening request is distinguished from verification that the remote page loaded; this test does not inspect website content or require the extension.

## Projects, Owner Mode and personal-browser update (2026-10-03)

- Full suite: **69 passed**, one upstream TestClient warning. Python compilation and JavaScript syntax checks pass.
- Owner Mode live fixture: `D:\Projects\JuneValidation-ec409cd2`. Python tests/run and static-web tests/build/server pass; edits, create/rename/copy/move, undo and project switching pass without ordinary approvals. Only two deliberate deletions and the unknown Galileo Bash command required review. No provider calls or external messages.
- Existing Galileo registration/inspection passes; its test command cannot run because Bash is missing. Source unchanged.
- Dashboard smoke passes with trust/settings controls and existing projects/Brain workflows.
- Actual extension DOM guards pass in isolated Chromium. Full Manifest V3 transport passes in a disposable profile: pair, authenticated poll/claim/result, new/active/read/type, external click denial.
- Personal Chrome install/pair and live YouTube/Google/X/WhatsApp/tab-count acceptance are **not verified**: computer-use approval review stopped browser control because it could not confidently determine the URL. User authorized installation; no attempt was made to bypass that block.
- See [setup and remaining limitations](browser-trust.md). Native GUI semantic classification, generated-artifact deletion classification and verified per-contact adapters are not complete.

## Latest layer: Presence and Brain

- **59 automated tests passed**, with one upstream Starlette/httpx deprecation warning. Added state priority, real job/tool/observation transitions, graph provenance/edges, negative-monitor coordinates, authenticated preference validation and persistence. Python compilation passes. The final task-failure indicator also passed the five focused presence tests; the browser smoke passed again after the empty-search fix.
- **Native fixture passed:** topmost orb, drag, saved position, actual mouse click-through to its own underlying window, orb click → overlay, hide/show, privacy/unconfigured-provider state, three send/focus-restoration cycles and graceful shutdown. Final full-process idle sample: 104.1 MB, 5.17% of one core over about three seconds, voice disabled. This is a short smoke sample, not a sustained performance benchmark.
- **Main runtime passed:** one orb visible, actual Ctrl+Space → overlay → Escape → previous foreground focus, local “June, show me your brain” completed without inference and requested the browser view. Gemini 2.5 Flash remains configured; after restart its status is configured_unverified, not a claim of fresh service availability. Wake listening is active according to the saved preference. Screen permission was disabled during the initial smoke and enabled in the final saved-settings health check; no continuous capture was added. Startup remains disabled.
- **Main resource sample:** desktop plus voice workers used 266.0 MB and 17.18% of one core over three seconds. CPU is expressed against one core, not whole-machine utilization. Browser polling and voice workers are included. Native process trees are measured, including the child interpreter; earlier launcher-only measurements were discarded.
- **Voice output passed:** SAPI speaking/completion events, actual June output peak 0.946, persistent worker, stop and privacy gates. Nine input names and three outputs enumerated. Human audibility and barge-in remain unverified.
- **Voice input:** synthetic WAV still produces ready, speech-detected and recognized June events. That fast file input produced no AudioLevelUpdated events, so it does not validate live microphone amplitude. The live recognizer event bridge is wired to the orb; human microphone testing remains necessary.
- **Browser passed:** authenticated dashboard, tasks, memory CRUD/pinning, privacy, settings, direct Brain link, graph search/filter/select, zoom/reset, and tracing at least six explicitly recorded fixture links; no JavaScript errors. Graph screenshots contain labelled fixture records, never fabricated production memories. Main graph endpoint returned 49 real records and seven recorded links at verification time.
- **Hardware scope:** one attached monitor. Negative origins and disconnected-monitor clamping pass unit tests; physical multi-monitor moves are unverified. Notification click routing and approval popup integration are implemented; an actual human click on a Windows notification has not been observed.

Evidence: `data/evidence/presence-live.json`, `desktop-live.json`, `audio-live.json`, `orb-live.png`, `overlay-live.png`, `brain.png`. Reproduce with `scripts/smoke_presence_live.py`, `smoke_desktop.py`, `smoke_audio.py`, `smoke_voice_events.py`, and `smoke_ui.py`. Presence tests use no external model calls. Main UI smoke opens a harmless fixture and the actual Brain dashboard; run only while June is idle.

## Current capability matrix

| Capability | Implemented | Tested | Live-tested | Limitations |
|---|---|---|---|---|
| Desktop/tray, graceful shutdown | Yes | Isolated lifecycle | Passed | User-session app, not a Windows service |
| Global palette | Yes | Three summon/send/focus-restoration cycles | Passed; main Ctrl+Space registered | Shortcut conflicts report unavailable; focus restoration is asynchronous |
| Gemini | Yes | Tool protocol and outages | 2.5 Flash tool round trip, image, coding and research passed | 3.8 returned 503; a later 2.5 repeat returned 429 RESOURCE_EXHAUSTED |
| Local/OpenAI brains | Preserved | Contract/boundaries | Earlier OpenAI request reached service | OpenAI credits absent; no local model configured |
| Durable working context/follow-ups | Yes | Project, command, error and stale restart state | Live coding sequence | Title-based project matching is labelled an inference |
| Continue previous work | Yes | Records/context | Git inspection machinery | Uses recorded tasks/events/next steps; cannot reconstruct unobserved work |
| Attention briefing | Yes, local | Offline and restart tests | Responded during background research | Calendar/email need connected accounts and approved queries |
| Coding workflow | Yes | Evidence gate and failures | Reproduce → approved edit → successful pytest passed | Disposable Python fixture, not Galileo/Unreal; later repeat quota-blocked |
| Memory and timelines | Yes | Persistence, provenance, conflicts, pinning | Dashboard create/pin/delete | Local semantic baseline; no large vector database or universal fact reconciliation |
| Background jobs | Yes | Queue, cancel, pause/fresh resume | Two-source research and concurrent local status | One action lane; resume is a new observed attempt |
| Research | Yes | Source-count gate | SQLite/Python official sources read and synthesized | Source quality and provider availability still matter |
| Browser | Yes | URL/failure policy | History/tabs/download/form masking/disconnection recovery passed | Isolated Chromium; no personal-browser account takeover |
| Screen capture | Yes | Sensor, consistency and stale guards | Real capture passed | Disabled in main app until user enables it |
| Vision | Yes | Path/size/privacy | Synthetic compiler error read correctly | Explicit upload approval; visual interpretation may be wrong |
| Full GUI click loop | Guarded implementation | Changed targets refused | **Incomplete** | Fixture lost foreground; June stopped instead of clicking another app |
| Voice/wake | Yes | Stop/privacy/PTT and WAV event bridge | WAV recognition and persistent SAPI worker passed | Human microphone, echo/barge-in and perceived latency unverified |
| Audio selection | Yes | Enumeration/initialization | 9 input names, 3 outputs enumerated | Names can include duplicate Windows host APIs; actual hardware needs verification |
| Reminders/proactivity | Yes | Due delivery, duplicates, quiet/privacy | Local runtime and stored completion notification | Human receipt of a toast is not proven by a stored notification |
| Brain/Neural Explorer | Yes | API and Chromium | Context/tools/usage/resources visible | No hidden reasoning or fabricated neural internals; GPU adapter absent |
| Host permissions and undo | Yes | Tampering, denial, stale targets, newer-user-edit preservation | Three fixture coding approvals | Arbitrary approved shell runs with Windows user authority; no blanket undo |
| Optional login startup | Yes, opt-in UI | Available code path | Not enabled | No startup entry or OS security changes made automatically |
| Email/calendar/GitHub | Existing adapters preserved | Unconfigured behavior | No accounts connected | No fabricated mailbox or meeting results |

The 54 tests include the original suite plus offline continuity; Gemini signatures and tool pairing; coding verification after the latest edit; refusal to count echo as verification; undo protecting newer user work; conflict provenance; hotkey validation; stale screen/after-image gates; pause/resume requiring fresh approval; command-registry change rejection; speech failure isolation; database-lock rollback/recovery; Talk returning to opted-in wake listening; and visible pause/resume/stop acknowledgements. The authenticated Brain endpoint exercises real Windows resource metrics.

## Desktop assistant acceptance loop: actual scope

| Requested steps | Evidence |
|---|---|
| 1. Start June | Main desktop running, Gemini selected, Ctrl+Space registered |
| 2. Say June | WAV recognition passes; room microphone wake unverified |
| 3–4. Recall Galileo | Real Galileo registry metadata exists; memory/context retrieval tested. Full spoken Galileo recall not observed |
| 5–6. Open it | Resolver and Explorer adapter implemented; palette submission/focus tested. No claim that this full spoken Galileo step passed |
| 7–9. Run and observe failure | Passed with registered command on an actual disposable Python fixture; not Unreal |
| 10–15. Diagnose, approve edit, rerun, verify | Passed with live Gemini: only calculator.py edited, unchanged tests then returned exit zero |
| 16. Remember tomorrow's work | Recognized-text voice callback → explicit memory and dated task covered in tests; no microphone claim |
| 17. Restart | Project/context/memory/task/schedule persist; permissions expire |
| 18–19. Retrieve planned work | Local attention retrieves the remembered task after reopening state in tests |

The later live coding repeat stopped with HTTP 429 RESOURCE_EXHAUSTED. The earlier successful fixture run remains valid, but **repeated live success has not been established**. No further provider retry was made after that quota result. Local commands remain available.

## Other integration scenarios

- **Screen loop:** capture and synthetic Gemini vision pass separately. An early complete-loop attempt reached vision, then refused changed focus/pixels. Later attempts found a different app foreground and stopped before upload/click. Full click → re-observe → verified outcome remains outstanding. Do not weaken the guard to obtain a pass.
- **Background agent:** live research read two explicit public documentation sources, persisted its answer and completion notification, and allowed a local status response during work. Cancellation and fresh-permission resume pass tests. Actual toast visibility needs human observation.
- **Proactivity:** tests cover due reminders without another chat prompt, duplicate suppression, quiet/privacy, restart and pause. No connected-calendar polling is claimed.

## Evidence

Sanitized reports: `data/evidence/gemini-live.json`, `coding-live.json`, `background-live.json`, `desktop-live.json`, `audio-live.json`, `screen-loop-live.json`. Images: `dashboard.png`, `settings.png`, `brain.png`; synthetic speech: `speech-test.wav`. Reports from a previous successful run do not establish current provider availability. `coding-live.json` is the earlier success; interpret subsequent runs alongside the quota result above and `coding-latest.json` when present.

Reproduction scripts are under `scripts/`: smoke_gemini, smoke_coding, smoke_background, smoke_desktop, smoke_screen_loop, smoke_browser, smoke_ui, smoke_audio, smoke_speech and smoke_voice_events. Live tests consume API quota or open fixture windows. Synthetic approval helpers are confined to these scripts and are not active in June's normal runtime.

Outstanding practical acceptance checks: uninterrupted human voice conversation, full foreground click loop, and a real Galileo build/repair. Account integrations need credentials. Provider quota is external. Conservative pixel checks may reject animation. A test exit zero proves the observed check succeeded, not complete correctness or test coverage.

---

# Historical first-phase validation — 2026-10-02

The material below is retained as the first-phase record. Its OpenAI blocker and 40-test count are superseded by the current matrix above.

## Automated suite

Command: `.\.venv\Scripts\python.exe -m pytest -q --basetemp D:\June\.cache\pytest`

Latest completed run: **40 passed**. There is one upstream Starlette/httpx TestClient deprecation warning; production uses HTTPX normally and Uvicorn, not TestClient.

Tests cover local persistence, semantic retrieval baseline, normalized memory deduplication, protected paths/traversal, stale file edits, oversized and binary files, argument schemas, secret redaction, host risk policy, multi-step agent execution, exact/single-use approval, argument tampering, denial, cancellation, shell timeout/output, bounded loops, failed-tool recovery, untrusted file instructions, privacy gates, restart recovery, expired restart approvals, singleton runtime lock, scheduled jobs/reminders, event subscriber failure isolation, notification suppression, file watchers, voice stop/privacy commands, bounded provider transport retry, recent-context selection, provider function-call parsing, private-network URLs, camera/screen disabled state, changed-window GUI rejection, unconfigured integrations and authenticated API Origin/Host checks.

These tests use deterministic brain fixtures for agent decisions. They establish runtime behavior, not the quality or safety of a live language model's reasoning.

## Live checks

| Check | Result |
|---|---|
| Native desktop and tray startup | Passed; authenticated local health reports running, microphone muted, screen capture off, zero jobs |
| Dashboard in real headless Chromium | Passed: authenticated load, task create/complete, memory create/forget, privacy toggle, settings, no JS errors |
| JavaScript syntax / Python compilation | Passed |
| Windows foreground/process observation | Passed |
| File → Python code → run → inspect exit/output | Passed |
| Project registry / situational briefing | Passed |
| Monitor capture | Passed, 1366×768; image deleted after dimensions check; no upload |
| Windows speech engine enumeration | en-US recognizer and two voices found |
| Local synthesis → recognition | Passed; recognized “June”, confidence about 0.70 |
| Asynchronous voice bridge | Passed with WAV input: ready, speech-detected event and recognized wake phrase; microphone remained off |
| Playwright browser navigation/read/tabs/download | Passed against a public documentation-example page; local synthetic download contents and D: destination verified |
| Independent research HTTP fetch/search | Passed |
| OpenAI request | Reached service; HTTP 429 `credit_balance_exhausted` |

Evidence: `data/evidence/dashboard.png`, `data/evidence/settings.png`, `data/evidence/speech-test.wav`. Smoke scripts live in `scripts/`. They print status only, never API keys or the dashboard bearer token.

## Requested acceptance scenarios

1. **Galileo memory/open/diagnose/fix/remind:** existing Galileo project was discovered and registered from README/uproject facts. No Galileo files were modified. Agent workflow mechanics and project/task persistence pass tests. The natural-language end-to-end scenario has not been validated against a live brain because API credits are exhausted.
2. **Look at screen/explain/fix:** local screen capture passes. Hosted visual reasoning is blocked by API credits; no screenshot was uploaded during validation.
3. **Research flying robots/store knowledge:** search, reading, approved tools and memory mechanics are implemented/tested separately. A live multi-source model synthesis has not been validated.
4. **What needs attention:** real local briefing aggregates tasks/projects/jobs/schedules/notifications and reports integration readiness. Calendar data is not invented. Natural-language summarization needs inference.
5. **Survive restart:** tests verify projects, memories, tasks and schedules survive. Unfinished jobs are marked interrupted, with permission requests expired instead of replayed.

## Remaining limitations

- Fund API access or configure a local tool-capable model before model-dependent acceptance tests can pass. No local inference weights were installed.
- Microphone recognition in your actual room, live speaker echo/barge-in, and camera hardware still need user-side validation.
- Email, calendar and GitHub need credentials; OAuth refresh is not implemented. Hardware is intentionally unconnected.
- Compact LSA/concept retrieval is a baseline; advanced semantic embeddings, contradiction resolution and large memory libraries need a stronger provider.
- Read-only/structured permissions are not a sandbox for an approved arbitrary shell command. DNS filtering is not a complete network sandbox.
- The agent has bounded time/context/step budgets and can stop for review. It cannot guarantee indefinite autonomous completion or recover every application state.
- No automatic boot/login service has been installed; launch June after reboot. Closing its native window keeps it in the tray.

The repository contains working implementations across the requested architecture, with honest capability boundaries. Full end-to-end completion is **not claimed** while inference and hardware/service validation remain outstanding.
