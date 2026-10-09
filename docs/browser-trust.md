# Personal browser and scoped Owner Mode

June extends the existing runtime, SQLite approval records, audit trail, cancellation and privacy gates. No provider call decides permission. `june/trust.py` is the host policy; no model tool can add a trust rule or change its risk classification.

## Browser modes

`browser.personal.open/new_tab/search` use Windows default-browser URL opening when the bridge is disconnected. This preserves your existing browser profile and does not start Playwright. Windows chooses the browser/window; June reports the opening as requested, not verified. The paired extension uses `chrome.tabs` in the existing Chrome/Edge profile. Opening WhatsApp focuses an existing matching tab when available; `new_tab` always creates a tab.

The extension is in `D:\June\extensions\june-browser-bridge`. Open your browser's Extensions page, enable Developer mode, choose **Load unpacked**, and select that directory. In June **Settings & Health → Permissions and trust → Personal browser**, create a one-time code. Open the extension popup, enter that code, and grant page access. No browser restart, remote-debugging flag or new profile is needed. Installation into the real profile was blocked by the computer-use approval review during this development session; pairing and real-session acceptance are still pending.

The first version uses port 8765. It connects only to `http://127.0.0.1:8765`. Pairing expires after five minutes and is single-use. The separate bridge bearer token is bound to the extension origin and cannot call administrative API routes. Revoke it from June Settings. The extension has no cookie, history, debugger, password-manager or remote-message access. Broad optional page permission is needed to inspect requested HTTP(S) pages; it does not continuously scrape tabs.

Tools cover active/list/activate/create/close/navigate tabs, title/URL, bounded visible text and controls, click/focus/type/submit, scrolling and play/pause. DOM actions are prepared in an isolated extension world, classified, approved if necessary, then executed using a short-lived single-use ticket bound to the exact element identity and fingerprint. Replaced or navigated targets fail closed. Password/payment/OTP fields, sensitive forms, authentication/payment pages and June administration are excluded. Input values are never returned. Unknown form actions remain consequential; known search fields and direct anchor navigation can run quietly. Playback remains subject to browser restrictions.

The existing isolated tools remain available as `browser.automation.*`; old `browser.*` names remain compatible. Use these or `web.search/read` for background research. They do not inherit personal cookies. Generic isolated-browser interactions still ask because their external consequences are not classified by the personal extension.

## Offline website commands

Basic open/go-to and search commands never require Gemini or another provider. Examples: `open coursera`, `open reddit`, `open wikipedia`, `open paulgraham.com`, `go to python.org`, `google quantum mechanics`, and `search youtube for quantum mechanics`.

The pure resolver in `june/browser_commands.py` uses a small alias table, a reviewed local site registry, and generic HTTP(S)/domain normalization. Unknown names become Google searches; June does not invent a `.com` address. URL paths, query strings and fragments are preserved. Unknown-name fallback leaves registered projects, built-in apps and local paths with their existing handlers. Navigation goes through the personal-browser tool and existing privacy/trust gates. Failed opening or denied permission never falls back to an LLM. Jobs and audit records expose `route=local_browser_command` and `provider_calls=0`.

## Permission behavior

The existing `D:\June` installation migrates to `owner_mode=true`, trusted workspace roots `D:\June` and `D:\Projects`, personal default browsing and automation background browsing. Other fixture installations retain strict defaults.

- Levels 0–1: ordinary observation and local actions run quietly, subject to privacy/sensor and app/domain gates.
- Level 2: trusted workspace create/edit/append/rename/move/copy/mkdir, recoverable undo, project creation, and recognized development commands run without repeated approvals.
- Level 3: external actions use `ASK`, `ALWAYS_ALLOW` or `DENY` service policies. Unknown services ask. Contacts are supported in policy data but only apply when an adapter supplies an independently observed contact identifier; the generic DOM bridge does not infer identity from a display name.
- Level 4: meaningful deletion, credentials, system operations and June's own policy/runtime files ask. Broad folder rules cannot bypass this level; narrowly remembered exact actions are supported.
- Level 5: payments, security changes and recognized critical shell operations always ask, even with remembered allow rules.

Both native and dashboard approval dialogs support once, remembered exact action, app, project, folder or service scopes, plus persistent denial. Scope rules apply to the reviewed tool, not arbitrary tools. Explicit denial wins. Settings displays and revokes rules and edits roots/apps/domains/shell categories/services. Critical rules cannot be remembered as allow. Existing approval records remain intact.

Shell classification accepts a small grammar for Python test/run, npm scripts, Git local inspection/staging, formatters, compilers, project-local dependency commands and similar development work. Unknown syntax, shell composition, global installs, external paths, push/reset/clean and administration ask. Python pip installs auto-allow only when using an explicit `.venv` interpreter. Task authorization records capture the selected project and permitted categories; every action rechecks current persistent policy, so task records cannot grant new authority.

**Boundary:** local development commands execute under your Windows account; this is not an OS sandbox. Tests, build scripts and dependency lifecycle scripts can execute arbitrary project code. Only trust projects whose code you permit to run. Native coordinate-based GUI actions still ask when the host cannot establish that they are ordinary navigation; a broad mouse/keyboard bypass would also bypass external-action safeguards. Per-contact messaging adapters, generated-artifact deletion classification, and automatic classification of arbitrary native GUI controls remain future work.

Page/file content is untrusted evidence and cannot create policy records. Privacy mode blocks browser/network/sensors. Stop cancels jobs and queued bridge work; already completed browser side effects cannot be undone by cancellation. Audit records include job, tool, arguments, effective risk, rule, target, result and timing. File backups and project timelines remain available.

## Validation

Run `.venv\Scripts\python.exe -m pytest -q`, `scripts/smoke_ui.py`, `scripts/smoke_browser_policy.py` and `scripts/smoke_projects.py`.

The project smoke runs real Python and Node tests/builds/server under a disposable `D:\Projects\JuneValidation-*` workspace. Routine steps require no approvals; deliberate deletion asks. It never sends a real message. Mock service decisions test allow/ask and critical escalation. The DOM smoke executes the extension's actual page function in isolated Chromium and checks protected fields, external/critical classification and stale-node refusal. The API tests verify origin, token scope, pairing replay and revocation. Real Chrome pairing/title/focus/tab-count checks are not yet verified because installation was blocked by the computer-use review.
