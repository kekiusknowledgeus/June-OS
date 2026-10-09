# June Presence

The existing Python runtime owns JuneState. The native Tk orb and overlay, tray and authenticated FastAPI dashboard observe that same runtime. No second agent or model is created for the UI. Closing the dashboard leaves June running; Exit June shuts it down.

## Controls

- Click the orb for the quick panel. A pending permission opens the exact-action review; approving still uses the host permission engine.
- Drag the orb to move it. Position persists in config.json and is clamped onto an attached monitor when placed. Negative monitor origins are supported.
- Right-click for Ask, Talk, Stop, task, Brain, dashboard, privacy, mute and hide actions.
- Ctrl+Space opens the overlay above the current application. Enter sends; Escape dismisses and restores the previous window. Shortcut changes apply after restart.
- Settings & Health → June Presence controls 80–240 px size, 0.3–1 opacity, visibility and idle click-through. Tray → Show orb also disables click-through so it can be moved again.
- “June, show me your brain” opens Brain through the local command path, including when the external provider is unavailable.
- “Start June when I log into Windows” is opt-in. It starts the existing desktop process minimized, including tray, orb, scheduler and opted-in voice. It has not been enabled automatically.

## State and audio

Privacy overrides every presence state. Pending approval, actual SAPI speaking, active listening, running tools/observation and processing follow in that order. A newly failed task displays ERROR for twelve seconds with its recorded error. When inactive, provider connectivity and microphone availability determine the idle, muted or unavailable indicator. A lit microphone dot means the microphone is active even during another state; the ring wakes when a wake phrase or push-to-talk session is active.

Input bars consume Windows SpeechRecognitionEngine AudioLevelUpdated values. The speech ring consumes the peak level of June's SAPI process through Windows Core Audio, rather than all system sound. No audio samples are captured by the output meter. If a matching session cannot be measured (for example on a non-default output), the API explicitly reports an engine-state animation fallback, not invented amplitude. Privacy and stop clear speech activity. Human microphone/echo and physical-device behavior still need acceptance testing.

The orb remains available without Gemini. “Configured, unverified” means exactly that; no background inference is made to animate or probe the UI. Network state is not independently probed. No weights, attention heads or hidden reasoning are shown.

## Brain and memory graph

The Brain page exposes provider identity, safe operational states, current context and goal, retrieved memories, tool activity, jobs, events, calls and measured resources. GPU telemetry is explicitly unavailable.

The graph is bounded to 180 local records. Project, memory, task, person, idea, decision, note, event, file and knowledge nodes link only through recorded metadata: project association, mentions, registered files, task dependencies and memory conflicts. Layout movement is decorative and labelled. Search and category filters reduce the view; selecting a node highlights its direct connections and exposes its source record. Drag nodes, pan empty space, use wheel/buttons to zoom, and Reset view to recenter. Keyboard Enter selects a focused node. Reduced-motion preferences disable layout animation.

NeuralInspector defines architecture, layers, parameter count, tensors, tokenization, logits, probabilities, attention maps, activations, training, gradients and runtime-metric interfaces. Gemini and the current generic local endpoint do not expose internal inspection. A future real LocalJuneBrain telemetry adapter must supply genuine values before model/layer/component/tensor navigation can be enabled.

## Runtime boundaries

The orb is a UI, not a permission bypass. Tool calls, approvals, cancellation, secrets and sensor gates remain in the existing runtime. Browser APIs retain bearer-token, host and origin checks. Active-app polling reads only foreground process identity every two seconds; it does not read titles, screenshots or document contents. Explicit summons retain the existing permission-aware context behavior.

Idle orb drawing is bounded to about eight frames per second; active states to about 24. Presence samples run every 150 ms, browser status every two seconds, and graph records refresh every ten seconds. Hidden orb drawing stops. No continuous vision calls are added. Notification clicks route to the relevant job or notification view; OS toast delivery remains dependent on Windows notification settings.

Implementation references: [Windows extended window styles](https://learn.microsoft.com/en-us/windows/win32/winmsg/extended-window-styles), [Microsoft input-level events](https://learn.microsoft.com/en-us/dotnet/api/system.speech.recognition.speechrecognitionengine.audiolevelupdated), [Pycaw Core Audio interfaces](https://github.com/AndreMiras/pycaw). See validation.md for the exact live-tested scope.
