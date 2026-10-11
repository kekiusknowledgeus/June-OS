"""Local Windows speech: no audio leaves the machine. Listening is opt-in."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Protocol


class SpeechProvider(Protocol):
    async def speak(self, text: str): ...
    async def stop(self): ...


async def available_devices():
    """Enumerate names only; never opens or records a microphone."""
    def inputs():
        import sounddevice as sd
        return sorted(set(d['name'] for d in sd.query_devices() if d['max_input_channels'] > 0))
    microphones = await asyncio.to_thread(inputs)
    script = "$v=New-Object -ComObject SAPI.SpVoice; @{outputs=@($v.GetAudioOutputs() | ForEach-Object {$_.GetDescription()}); voices=@($v.GetVoices() | ForEach-Object {$_.GetDescription()})} | ConvertTo-Json -Compress"
    process = await asyncio.create_subprocess_exec('powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), 10)
        output = json.loads(stdout.decode('utf-8-sig', errors='replace')) if process.returncode == 0 else {'outputs': [], 'voices': [], 'error': 'Windows speech enumeration unavailable'}
        return {'microphones': microphones, **output}
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


class WindowsSpeech:
    def __init__(self, config, on_text):
        self.config, self.on_text = config, on_text
        self.listener = self.speaker = self.reader = None
        self.ptt_timeout = None
        self.state = "muted"
        self.error = ""
        self.awake_until = 0
        self.push_to_talk = False
        self.audio_stream = None
        self.audio_writer = None
        self.audio_queue = None
        self.speaking = False
        self.input_level = 0
        self.speaker_reader = None
        self.output_meter = None
        self.kokoro_process = None
        self.kokoro_task = None
        self.kokoro_id = 0
        self.kokoro_text = ""
        self.first_audio_ms = None
        self.speech_lock = asyncio.Lock()
        self.kokoro_watchdog = None
        self.active_backend = None

    def _kokoro_paths(self):
        """Use only the separate test environment. The original D:/June is unaffected."""
        root = self.config.root
        python = root / ".venv-voice" / "Scripts" / "python.exe"
        model = root / "models" / "kokoro" / "kokoro-v1.0.int8.onnx"
        voices = root / "models" / "kokoro" / "voices-v1.0.bin"
        return python, model, voices

    def _kokoro_available(self):
        python, model, voices = self._kokoro_paths()
        return all(p.is_file() for p in (python, model, voices))

    async def start(self, push_to_talk=False):
        if self.config.privacy or not self.config.voice_enabled:
            raise PermissionError("Microphone disabled")
        if self.listener and self.listener.returncode is None:
            self.push_to_talk = push_to_talk
            self.awake_until = time.monotonic() + 30 if push_to_talk else 0
            self._set_ptt_timeout(push_to_talk)
            return
        script = Path(__file__).parent / "scripts/listen.ps1"
        env = dict(os.environ)
        if self.config.speech_input_device:
            env["JUNE_INPUT_STREAM"] = "1"
        self.listener = await asyncio.create_subprocess_exec("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script.read_text("utf-8"), stdin=subprocess.PIPE if self.config.speech_input_device else subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if self.config.speech_input_device:
            try:
                await self._start_selected_microphone()
            except Exception:
                await self.stop()
                self.state = "unavailable"
                self.error = "Selected microphone could not be opened"
                raise RuntimeError(self.error) from None
        # Output workers start on demand; listening never depends on output startup.
        self.state = "starting"
        self.push_to_talk = push_to_talk
        self.awake_until = time.monotonic() + 30 if push_to_talk else 0
        self.reader = asyncio.create_task(self._read())
        self._set_ptt_timeout(push_to_talk)

    def _set_ptt_timeout(self, enabled):
        if self.ptt_timeout:
            self.ptt_timeout.cancel()
            self.ptt_timeout = None
        if enabled:
            async def expire():
                await asyncio.sleep(30)
                if self.push_to_talk:
                    await self._finish_ptt()
            self.ptt_timeout = asyncio.create_task(expire())

    async def _finish_ptt(self):
        if self.config.always_listen and self.config.voice_enabled and not self.config.privacy:
            self.push_to_talk = False
            self.state = 'wake listening'
            if self.ptt_timeout and self.ptt_timeout is not asyncio.current_task():
                self.ptt_timeout.cancel()
            self.ptt_timeout = None
        else:
            await self.stop()

    async def _read(self):
        process = self.listener
        try:
            while line := await process.stdout.readline():
                data = json.loads(line.decode("utf-8-sig"))
                if 'audio_level' in data:
                    self.input_level = max(0, min(1, data['audio_level'] / 100))
                    continue
                if data.get("status") == "ready":
                    self.state = "listening" if self.push_to_talk else "wake listening"
                    continue
                if data.get("error"):
                    self.error = data["error"]
                    self.state = "unavailable"
                    break
                if data.get("speech_detected"):
                    await self.stop_speaking()
                    continue
                text = data.get("text", "").strip()
                if not text or data.get("confidence", 0) < .45:
                    continue
                low = text.lower().strip(" .!?")
                if low in {"june stop", "stop", "cancel", "stop that task", "pause everything", "cancel that", "don't do that", "june privacy mode", "privacy mode"}:
                    await self.on_text(low)
                    continue
                if low == "june" or low.startswith(("june ", "june,", "june.")):
                    self.awake_until = time.monotonic() + 30
                    text = text[4:].strip(" ,.!?")
                    if not text:
                        await self.speak("Yeah?")
                        continue
                elif not self.push_to_talk and time.monotonic() > self.awake_until:
                    continue
                await self.stop_speaking()
                await self.on_text(text)
                self.awake_until = time.monotonic() + 30
                if self.push_to_talk:
                    await self._finish_ptt()
                    if self.state == 'muted':
                        break
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = type(exc).__name__
            self.state = "unavailable"
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            if self.state not in {"muted", "unavailable"}:
                self.state = "unavailable"
                self.error = "Speech engine stopped; check Windows speech language and microphone"

    async def speak(self, text):
        async with self.speech_lock:
            if self.config.privacy or not self.config.voice_enabled or not text.strip():
                return
            await self.stop_speaking()
            request_id = self.kokoro_id
            backend = self.config.speech_backend
            if backend not in {"sapi", "kokoro", "auto"}:
                raise ValueError("Unknown speech backend")
            if backend in {"kokoro", "auto"} and self._kokoro_available():
                try:
                    await self._ensure_kokoro()
                    if request_id != self.kokoro_id or self.config.privacy or not self.config.voice_enabled:
                        return
                    self.kokoro_text = text[:8000]
                    self.first_audio_ms = None
                    self.kokoro_process.stdin.write((json.dumps({
                        "command": "speak", "id": self.kokoro_id,
                        "text": self.kokoro_text,
                    }) + "\n").encode("utf-8"))
                    await self.kokoro_process.stdin.drain()
                    self.speaking = True
                    self.active_backend = 'kokoro'
                    self.kokoro_watchdog = asyncio.create_task(self._watch_first_audio(request_id, text))
                    return
                except (OSError, RuntimeError, TimeoutError, ValueError):
                    await self._close_kokoro()
                    self.error = "Kokoro unavailable; using Windows speech"
            elif backend == "kokoro":
                self.error = "Kokoro files missing; using Windows speech"
            await self._sapi_speak(text)

    async def _watch_first_audio(self, request_id, text):
        await asyncio.sleep(max(.1, self.config.kokoro_first_audio_timeout))
        if request_id != self.kokoro_id or self.first_audio_ms is not None or self.active_backend != 'kokoro':
            return
        await self._close_kokoro()
        if request_id == self.kokoro_id and self.config.voice_enabled and not self.config.privacy:
            self.error = 'Kokoro exceeded first-audio deadline; using Windows speech'
            try:
                await self._sapi_speak(text)
            except (OSError, RuntimeError):
                self.error = 'Speech output unavailable; reply remains available as text'

    async def _ensure_kokoro(self):
        if self.kokoro_process and self.kokoro_process.returncode is None:
            return
        python, model, voices = self._kokoro_paths()
        process = await asyncio.create_subprocess_exec(
            str(python), str(Path(__file__).with_name("kokoro_speak.py")),
            str(model), str(voices), str(self.config.kokoro_threads),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.kokoro_process = process
        try:
            line = await asyncio.wait_for(process.stdout.readline(), 30)
            if not json.loads(line).get("ready"):
                raise RuntimeError("Kokoro worker did not become ready")
        except BaseException:
            await self._close_kokoro()
            raise
        self.kokoro_task = asyncio.create_task(self._kokoro_events(process))

    async def _kokoro_events(self, process):
        try:
            while line := await process.stdout.readline():
                event = json.loads(line)
                if event.get("id") != self.kokoro_id:
                    continue
                if "first_audio_ms" in event:
                    self.first_audio_ms = event["first_audio_ms"]
                if event.get("done") or event.get("error"):
                    self.speaking = False
                if event.get("error"):
                    self.error = "Kokoro synthesis failed"
                    # Avoid repeating already played speech on a mid-utterance failure.
                    if self.first_audio_ms is None and self.config.voice_enabled and not self.config.privacy:
                        await self._sapi_speak(self.kokoro_text)
        except (ValueError, OSError, RuntimeError):
            self.error = "Kokoro worker unavailable"
        finally:
            if self.kokoro_process is process and self.active_backend == 'kokoro':
                self.speaking = False

    async def _close_kokoro(self):
        task, self.kokoro_task = self.kokoro_task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        process, self.kokoro_process = self.kokoro_process, None
        if process and process.returncode is None:
            process.kill()
            await process.wait()

    async def _sapi_speak(self, text):
        if self.config.privacy or not self.config.voice_enabled:
            return
        request_id = self.kokoro_id
        await self._ensure_speaker()
        if request_id != self.kokoro_id or self.config.privacy or not self.config.voice_enabled:
            return
        self.active_backend = 'sapi'
        self.speaker.stdin.write((json.dumps({"command": "speak", "text": text[:8000]}) + "\n").encode("utf-8"))
        await self.speaker.stdin.drain()

    async def _ensure_speaker(self):
        if self.speaker and self.speaker.returncode is None:
            return
        # A persistent local SAPI worker avoids loading the speech engine per sentence.
        script = Path(__file__).parent / "scripts/speak.ps1"
        env = {**os.environ, "JUNE_SPEECH_OUTPUT": self.config.speech_output_device, "JUNE_SPEECH_VOICE": self.config.speech_voice}
        self.speaker = await asyncio.create_subprocess_exec("powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script.read_text("utf-8"), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            ready = await asyncio.wait_for(self.speaker.stdout.readline(), 8)
            if ready.strip() != b"ready":
                raise RuntimeError("Speech output initialization failed")
            self.speaker_reader = asyncio.create_task(self._speaker_events(self.speaker))
            from .audio_meter import OutputMeter
            self.output_meter = OutputMeter(self.speaker.pid)
        except BaseException:
            await self._close_speakers()
            if asyncio.current_task().cancelling():
                raise
            self.error = "Speech output unavailable; check selected output device and voice"
            raise RuntimeError(self.error) from None

    async def _speaker_events(self, process):
        try:
            while line := await process.stdout.readline():
                event = json.loads(line.decode('utf-8-sig'))
                if 'speaking' in event and self.active_backend == 'sapi':
                    self.speaking = bool(event['speaking'])
        except (ValueError, OSError):
            self.error = 'Speech status stream unavailable'
        finally:
            if self.active_backend == 'sapi':
                self.speaking = False

    async def _start_selected_microphone(self):
        import sounddevice as sd
        loop = asyncio.get_running_loop()
        self.audio_queue = asyncio.Queue(maxsize=64)
        def enqueue(data):
            if not self.audio_queue.full():
                self.audio_queue.put_nowait(data)
        def callback(data, frames, timing, status):
            loop.call_soon_threadsafe(enqueue, bytes(data))
        devices = sd.query_devices()
        selected = next((i for i, d in enumerate(devices) if d["name"] == self.config.speech_input_device and d["max_input_channels"] > 0), None)
        if selected is None:
            raise RuntimeError("Selected microphone not found")
        self.audio_stream = sd.RawInputStream(device=selected, samplerate=16000, channels=1, dtype="int16", blocksize=1600, callback=callback)
        self.audio_stream.start()
        async def pump():
            while True:
                chunk = await self.audio_queue.get()
                self.listener.stdin.write(chunk)
                await self.listener.stdin.drain()
        self.audio_writer = asyncio.create_task(pump())

    async def stop_speaking(self):
        self.kokoro_id += 1
        task, self.kokoro_watchdog = self.kokoro_watchdog, None
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self.speaking and self.kokoro_process:
            # Native inference cannot be cancelled safely in-thread. Terminate
            # only on interruption; completed utterances retain the warm model.
            await self._close_kokoro()
        self.speaking = False
        self.active_backend = None
        for process in (self.kokoro_process, self.speaker):
            if process and process.returncode is None:
                try:
                    process.stdin.write(b'{"command":"stop"}\n')
                    await process.stdin.drain()
                except (BrokenPipeError, ConnectionResetError):
                    pass

    async def _close_speakers(self):
        await self._close_kokoro()
        if self.output_meter:
            self.output_meter.stop()
            self.output_meter = None
        if self.speaker and self.speaker.returncode is None:
            self.speaker.kill()
            await self.speaker.wait()
        self.speaker = None
        if self.speaker_reader and self.speaker_reader is not asyncio.current_task():
            self.speaker_reader.cancel()
            await asyncio.gather(self.speaker_reader, return_exceptions=True)
        self.speaker_reader = None

    async def stop(self):
        self.state = "muted"
        self.input_level = 0
        if self.ptt_timeout and self.ptt_timeout is not asyncio.current_task():
            self.ptt_timeout.cancel()
        self.ptt_timeout = None
        if self.audio_stream:
            self.audio_stream.stop()
            self.audio_stream.close()
            self.audio_stream = None
        if self.audio_writer:
            self.audio_writer.cancel()
            await asyncio.gather(self.audio_writer, return_exceptions=True)
            self.audio_writer = None
        await self.stop_speaking()
        await self._close_speakers()
        if self.listener and self.listener.returncode is None:
            self.listener.kill()
            await self.listener.wait()
        if self.reader and self.reader is not asyncio.current_task():
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
        self.listener = None
