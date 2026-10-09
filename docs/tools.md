# Tools

The host-owned registry maps schemas to real async callables. OpenAI-safe names replace `.` with `__` only at the provider boundary. Unknown tools, extra arguments, missing required arguments and wrong primitive types fail.

| Group | Implemented operations |
|---|---|
| Files | list, UTF-8 read, hash-checked write/append/create, mkdir, copy/move/rename, single-file delete, wildcard/text search, metadata |
| Code | All file tools, read-only Git status/diff/log/branch, approved PowerShell builds/tests/debug commands |
| Windows | Active window/processes, open curated apps or allowed paths, focus window, terminate process, clipboard, click/type/hotkey/scroll |
| Vision | Monitor/active-window PNG capture, optional camera frame, approval-gated model image analysis |
| Browser | Visible isolated Chromium, named tabs, navigate/read/controls, click/fill/select/press/scroll/back/download, screenshot |
| Research | Public search and bounded HTTP text reading, kept separate from browser state |
| Records | Memory search/proposals, project registry, tasks/dependencies/deadlines, briefing |
| Automation | One-shot/repeating reminders, scheduled prompts, file/process watches |
| Services | Generic integration execution for email, calendar and GitHub |

PowerShell returns stdout, stderr, exit code and duration, with bounded output and a clean environment excluding secret-like variable names. Timeout/cancellation kills the tracked process tree. A process that deliberately escapes its tree is not contained by an OS sandbox. Known Git inspection bypasses external diff/textconv and fsmonitor configuration.

GUI actions require a recent capture ID and exact title/handle/bounds/pixel checks after approval. They return `action_performed_outcome_unverified`; further GUI actions require analysis of the after-image. PyAutoGUI's top-left-corner fail-safe remains enabled. Animated or changed windows can be refused conservatively. Text typing uses the keyboard's ASCII-oriented mapping; Unicode should use approved clipboard access and paste. Drag gestures are not implemented.

`project.inspect/open/run` provide registered project adapters for Git, Explorer, VS Code and Unreal where installed. The host binds a project's command and working directory before requesting approval; changes to the registry invalidate that action. Open means a launch request, not proof that an application loaded successfully.

File writes retain local previous-content manifests in `data/backups`. `file.undo` only restores/removes a file if its current hash still matches June's edited version. It refuses to overwrite newer user work. Transfers, arbitrary shell commands, external submissions and deletion do not promise undo.

Adding tools requires defining a schema, a host-side risk classification, an implementation, relevant tests, and registration in the runtime. Never trust a risk classification supplied by the model. Tool exceptions are returned as failure observations, allowing replanning. Side effects are not automatically retried.
