# June OS development audit — 11 October 2026

## Scope and provenance

Work stayed in `D:\June-V0-Test`. The supplied directory initially had no Git
metadata. Its Git metadata was reconstructed from
`mayank69420/June-OS`, branch `feature/june-v0-experimental-brain`, at
`9b382ecf5f08463ff9ace9daf8cc3dde7a192197`, without checking out or overwriting
working files. Local edits already differed from that commit. A source backup
of the supplied `june/` and `extensions/` folders is in
`.cache/audit-original/` (ignored, not published).

The missing `pyproject.toml` and `tests/test_groq.py` were recovered from that
branch. Existing local changes are included in the resulting implementation;
they were not silently reset to the remote version. No push or merge was made.
The final commit attempt was blocked by missing Git author name/email. All
changes remain staged on the experimental branch. No author identity was
invented or global Git configuration changed; supply the desired repository-local
identity and commit the reviewed staged changes when returning.
Existing model weights and the original `v0_model.py` architecture were preserved.
Tracked generated Python bytecode was removed from the Git index only; files
remain on disk. Ignore rules prevent future commits of runtime data, local
configuration, model weights, environments and caches.

No live account actions, microphone recording, screenshots, browser-tab
interaction, startup changes, or credential lookup were used for validation.
Audio performance tests synthesized a fixed public phrase in memory, silently.
`D:\June` was not read or modified.

## Implemented changes

### Speech

- New configuration and Settings selector: `sapi`, `kokoro`, `auto`.
  SAPI is the default for configurations without an explicit speech backend.
- SAPI's process survives normal interruptions via its existing stop command.
  Previously the host killed and reloaded it repeatedly.
- Kokoro uses a persistent worker and retains ONNX weights between completed
  utterances. Active interruption terminates the worker to reliably cancel
  native inference and playback; the next Kokoro request loads a new worker.
- Speech is split into sentence/word chunks of at most 180 characters, so a
  long answer does not require full synthesis before playback. No shared debug
  WAV is written. Already-existing debug audio was left untouched.
- ONNX runs on CPU with two intra-op threads, one inter-op thread, sequential
  execution and disabled intra-op spinning. `kokoro_threads` accepts 1–8.
- First-audio synthesis deadline defaults to 8 seconds after worker readiness.
  If no audio has started, the worker is stopped and SAPI receives the text.
  Already-started speech is not replayed by this timeout fallback.
- Generation IDs suppress stale worker events. Privacy, disable, stop and
  preference changes invalidate output; changing audio preferences closes old
  workers. Worker startup has a separate 30-second maximum.
- Health exposes the selected backend and last Kokoro first-audio synthesis
  timing. It is not a microphone-measured audible latency.

**Measured limitation:** this machine has four logical CPUs. The installed
INT8 model remains much slower than real time. For `June is ready.` (1.172 s
of generated audio), silent runs measured:

| Mode | Model load | Synthesis |
| --- | ---: | ---: |
| Original library defaults | 3.969 s | 16.807 s |
| Two threads, cold | 5.337 s | 16.744 s |
| Two threads, warm | already loaded | 16.394 s |
| One thread | 4.995 s | 27.569 s |
| Four threads | 4.326 s | 17.456 s |

These are diagnostic single runs, not statistical benchmarks; some ran while
regression tests were active. Profiling a separate call attributed 18.644 s to
ONNX execution and 0.307 s to phonemization. Persistent loading removes reload
cost but **does not fix the underlying INT8 graph's synthesis throughput**.
Use SAPI for responsiveness on this machine. Kokoro's next investigation is
graph/operator profiling and a separately reviewed model/runtime alternative.
No model downloads or GPU installs were performed.

### Groq and tool execution

- Reuses one HTTP connection pool and closes it with the runtime.
- Removes unconditional model-specific reasoning parameters that can cause
  HTTP 400 when changing models.
- Groups consecutive tool calls into one assistant message followed by all
  corresponding tool results, including the generic local chat adapter.
- Requires a terminal stream marker and successful finish reason; malformed,
  empty, truncated and interrupted streams cannot dispatch partial tools.
- Assembles fragmented calls by index; bounds call count and argument size;
  rejects duplicate IDs and tools outside the advertised selection.
- Captures numeric usage from either standard or Groq stream metadata.
- Rate limits create a monotonic cooldown, parse fractional/date Retry-After
  values, and avoid another request or daily-budget debit during cooldown.
  No automatic replay of side effects occurs. Error text no longer falsely
  claims that no earlier step ran.
- Retries pre-response transport/temporary server failures at most once through
  the runtime. Interrupted partial streams pause for review instead of retrying.
- Mixed coding/browser requests retain later capability groups instead of
  losing them to an 18-tool slice. Browser navigation/activation/scroll/media
  and desktop vision verification tools are available when relevant.
- Validates tool argument shapes before host preparation or permission prompts.
- Supplies canonical call history when an adapter omits raw records. Stops the
  remainder of a tool batch after failure/denial and records skipped results,
  letting the next inference replan instead of using missing dependencies.
- Repeated read-only observations are permitted within the overall step budget;
  repeated side-effect requests still trip the duplicate-action guard.

Protocol references used during review:
[Groq compatibility](https://console.groq.com/docs/openai),
[rate limits](https://console.groq.com/docs/rate-limits), and
[tool use](https://console.groq.com/docs/tool-use/overview).
No paid/live Groq request was made, and configured model availability remains
unverified.

### Routing, browser and desktop

- Compound open/read/click requests reach the agent loop instead of becoming a
  web search. The explicit YouTube-and-search shortcut remains supported.
- Memory searches stay local. Tab-list commands use exact patterns rather than
  matching `tab` inside unrelated words such as `database`.
- `read current page` / `read this tab` actually reads the page body.
- Browser Bridge claims are one-use; cancelled, duplicate and unclaimed results
  are rejected. Revocation/privacy/shutdown cancel queued work. Queue overflow
  reports a controlled error.
- Extension fetches have deadlines. Uncertain action results are not retried.
- Controls without IDs receive generated CSS paths. Disabled/ambiguous controls
  and navigation races fail before interaction. Existing fingerprint checks
  and one-use action tickets remain enforced.
- Windows focus verifies the target handle. Unsupported Unicode typing fails
  explicitly rather than silently losing characters; hotkeys validate keys.
- An action whose after-screenshot fails still closes the verification gate.
  A new capture can be analyzed to recover before another input action.
- Default roots now resolve to this installed checkout (or explicit root/env),
  avoiding accidental fallback to `D:\June`.
- Groq model names display correctly in the Brain/Presence inspector.

### Original June V0

The character-level architecture and checkpoint layout remain separate from
Groq. `provider: june_v0` and the `v0` CLI remain available. The model still
returns zero tool calls and refuses vision. Output now labels itself as an
experimental text sample, rather than claiming to answer a factual question.
Existing provider configuration is not silently switched to a cloud service.

## Audit coverage and remaining risks

| Area | Review/verification | Remaining limitation |
| --- | --- | --- |
| Voice worker, SAPI, recognition lifecycle | Code review, mocked lifecycle/deadline tests, silent ONNX profiling | Audible playback, barge-in, chosen devices and microphone need an attended test; Kokoro uses Windows default output and `af_heart` |
| Groq / local chat / runtime | Offline streaming fixtures, retry/cooldown, multi-step and history tests | Live model compatibility, quotas and network latency unverified; no automatic context compaction |
| Personal browser / extension / API | Python request lifecycle tests and Node mocked Chrome/DOM tests | Real MV3 suspension, pairing, navigation/loading, iframes and shadow DOM need attended testing; bridge currently assumes port 8765 |
| Windows controls | Mocked capture/focus/input guards, existing stale-image tests | Pixel equality intentionally rejects animation; Unicode typing requires a future native input adapter |
| Files / projects / shell / trust | Existing hash-check, undo, path, command-binding, permissions and cancellation regression tests; source review | Shell execution is not an OS sandbox. Trusted project scripts can run arbitrary code. Detached child process cleanup still needs stronger Windows job-object isolation |
| Web research / isolated Playwright | Source review and SSRF rejection tests | DNS validation and actual connection are separate; DNS-rebinding defense is incomplete. Isolated-browser downloads and page fields need broader live adversarial testing |
| Store / memory / context / workflows | Persistence, lock rollback, conflict, stale-context and verification tests | Semantic SVD is synchronous and can stall on a large corpus; no retention/compaction policy |
| API / dashboard / desktop / presence | Authentication/origin tests, settings tests, JS syntax checks, source review | No attended tray/hotkey/UI smoke test; framework deprecation warning remains |
| Schedules / notifications / watchers | Existing durable schedule, cooldown, privacy and pause tests | No long-duration fault-injection or reboot test |
| Email / calendar / GitHub / hardware / camera | Source review and unavailable/permission tests | No live services/devices tested; thread-based external operations cannot guarantee cancellation once dispatched |
| V0 model | Existing tiny synthetic checkpoint test, text-only/zero-tool contract | Original production weights were not loaded or modified; it is not instruction-trained |

This is a repository-wide engineering audit and tested implementation pass,
not a claim that all real-world workflows are production-verified.

## Validation and review

Baseline: 110 Python tests passed. Final: 146 Python tests and 5 Node tests passed.
Commands and the remaining upstream deprecation warning are recorded in
`docs/validation.md`. Tests use workspace-local temporary data and synthetic
credentials; external socket connections are blocked. Loopback is allowed for
Windows asyncio's socketpair. Browser/desktop action tests use mocks.

Review the restored packaging/Groq tests, included pre-existing source edits,
SAPI default, Kokoro fallback deadline, compound-command routing, batch failure
semantics, and extension update. Reloading the unpacked extension and attended
live audio/browser/Groq tests are pending. No push, main-branch merge, startup
installation, purchases or outgoing messages are authorized by this work.
