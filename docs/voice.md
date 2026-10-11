# Voice

Voice uses local Windows `System.Speech` recognition and selectable persistent
SAPI/Kokoro synthesis workers. Microphone audio stays local; accepted transcripts
enter the same conversation as typed requests and may reach the selected brain.
The 2026-10-11 pass verified mocked lifecycle and privacy behavior plus silent
Kokoro synthesis. Live microphone accuracy, audibility and echo still need
attended validation.

Choose **Speech backend** in Settings:

- `sapi`: Windows speech, the default for low latency; honors Windows voice/output preferences.
- `kokoro`: local neural voice in `.venv-voice`; uses `af_heart` and Windows default output.
- `auto`: chooses Kokoro when its local files exist, otherwise SAPI.

Both Kokoro modes fall back to SAPI if initialization fails or first synthesis
exceeds `kokoro_first_audio_timeout` (8 seconds after worker readiness).
`kokoro_threads` (default 2, range 1–8) controls ONNX CPU parallelism. These two
advanced options can be set in this checkout's `config.json`. Worker startup
itself has a separate 30-second timeout. Audio preferences apply immediately;
input-device changes still require restarting listening.

Kokoro requires `.venv-voice/Scripts/python.exe`, `kokoro-onnx` with
`Kokoro.from_session`, ONNX Runtime and SoundFile, plus
`models/kokoro/kokoro-v1.0.int8.onnx` and `voices-v1.0.bin`. No downloads occur
automatically. Models remain loaded between completed utterances. Interrupting
active native inference terminates that worker; the next request reloads it.
Audio is played from memory and no new debug WAV is retained.

The installed INT8 model is still slower than real time on the test machine;
see [measurements and limitations](development-audit-2026-10-11.md). Choose SAPI
for fast output. The health first-audio metric measures synthesis completion,
not speaker audibility or end-to-end LLM-to-speech latency.

Open Settings & health, enable `voice_enabled`, then select Talk for a single utterance or enable `always_listen` for hands-free mode. The visible status transitions through starting, wake listening/listening, muted or unavailable. In wake mode, saying “June” starts a 30-second conversational window; saying only June produces “Yeah?”. Disable voice or use the tray's Mute action to release the microphone.

Settings lists available microphone, SAPI output and voice names. Blank preferences use Windows defaults. Selected microphone capture uses local 16 kHz mono PCM through sounddevice. Toggle voice off/on after changing devices. A Talk request returns to wake listening when always_listen is enabled; it no longer silently stops the opted-in listener. The shortcut preference takes effect after restarting June.

`June stop`, `stop`, `cancel that` and `don't do that` cancel current jobs and speech. `June privacy mode` stops sensing and external access. Speech-detected events stop synthesis for barge-in; this is a basic local implementation without acoustic echo cancellation. A headset helps avoid June hearing her own speaker output. It is not claimed to match a low-latency neural realtime voice model.

The Windows adapter starts fixed application-owned PowerShell commands without changing execution policy. User text is passed over stdin to synthesis, never interpolated into executable shell code. Speech recognition/synthesis are behind the `SpeechProvider` boundary and can be replaced by local neural models. The backend catches recognizer failure and reports unavailable instead of claiming to listen.

For offline lifecycle regression coverage, run
`.\.venv\Scripts\python.exe -m pytest tests/test_reliability.py -q`.
No live microphone or audio device is opened by these tests.

To reproduce silent performance measurements:

```powershell
.\.venv-voice\Scripts\python.exe scripts/benchmark_speech.py --threads 2
.\.venv-voice\Scripts\python.exe scripts/benchmark_speech.py --original
```

The benchmark prints JSON timing data and never plays or saves its audio.
