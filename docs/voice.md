# Voice

Voice uses local Windows `System.Speech` recognition and a persistent SAPI synthesis worker. Microphone audio stays local; accepted transcripts enter the same June conversation as typed requests and may reach the selected brain. Device enumeration, speech-worker readiness, stopping/privacy, and WAV recognition passed. Live microphone accuracy, echo behavior, audibility and room noise still need human validation.

Open Settings & health, enable `voice_enabled`, then select Talk for a single utterance or enable `always_listen` for hands-free mode. The visible status transitions through starting, wake listening/listening, muted or unavailable. In wake mode, saying “June” starts a 30-second conversational window; saying only June produces “Yeah?”. Disable voice or use the tray's Mute action to release the microphone.

Settings lists available microphone, SAPI output and voice names. Blank preferences use Windows defaults. Selected microphone capture uses local 16 kHz mono PCM through sounddevice. Toggle voice off/on after changing devices. A Talk request returns to wake listening when always_listen is enabled; it no longer silently stops the opted-in listener. The shortcut preference takes effect after restarting June.

`June stop`, `stop`, `cancel that` and `don't do that` cancel current jobs and speech. `June privacy mode` stops sensing and external access. Speech-detected events stop synthesis for barge-in; this is a basic local implementation without acoustic echo cancellation. A headset helps avoid June hearing her own speaker output. It is not claimed to match a low-latency neural realtime voice model.

The Windows adapter starts fixed application-owned PowerShell commands without changing execution policy. User text is passed over stdin to synthesis, never interpolated into executable shell code. Speech recognition/synthesis are behind the `SpeechProvider` boundary and can be replaced by local neural models. The backend catches recognizer failure and reports unavailable instead of claiming to listen.

To validate without microphone access: `.\.venv\Scripts\python.exe scripts\smoke_speech.py`. It creates `data/evidence/speech-test.wav` and recognizes from that file; it does not play sound or start continuous capture.
