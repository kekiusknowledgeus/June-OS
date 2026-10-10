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
        if not self._kokoro_available():
            await self._ensure_speaker()
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

    async def _ensure_kokoro(self):
        if self.kokoro_process and self.kokoro_process.returncode is None:
            return self.kokoro_process
        python, model, voices = self._kokoro_paths()
        process = await asyncio.create_subprocess_exec(
            str(python), str(Path(__file__).with_name("kokoro_speak.py")),
            str(model), str(voices),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            ready = await asyncio.wait_for(process.stdout.readline(), timeout=35)
            data = json.loads(ready) if ready else {}
            if data.get("status") != "ready":
                raise RuntimeError("Kokoro voice worker did not initialize")
        except Exception:
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise
        self.kokoro_process = process
        return process

    async def speak(self, text):
        if self.config.privacy or not self.config.voice_enabled:
            return
        if self._kokoro_available():
            # Cancel any playing reply; reuse the warm worker when it is idle.
            if self.kokoro_task:
                await self.stop_speaking()
            try:
                process = await self._ensure_kokoro()
                process.stdin.write((json.dumps({"command": "speak", "text": text[:1500]}) + "\n").encode("utf-8"))
                await process.stdin.drain()
                self.speaking = True
                self.kokoro_task = asyncio.create_task(self._finish_kokoro(process))
                return
            except Exception as exc:
                self.error = "Kokoro unavailable: " + str(exc)[:180]
                await self.stop_speaking()
        await self._sapi_speak(text)

    async def _finish_kokoro(self, process):
        try:
            line = await process.stdout.readline()
            data = json.loads(line) if line else {}
            if data.get("status") != "done":
                raise RuntimeError(data.get("error", "Kokoro worker stopped"))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.error = "Kokoro playback failed: " + str(exc)[:180]
        finally:
            self.speaking = False
            if self.kokoro_task is asyncio.current_task():
                self.kokoro_task = None

    async def _sapi_speak(self, text):
        await self._ensure_speaker()
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
        except Exception:
            await self.stop_speaking()
            self.error = "Speech output unavailable; check selected output device and voice"
            raise RuntimeError(self.error) from None

    async def _speaker_events(self, process):
        try:
            while line := await process.stdout.readline():
                event = json.loads(line.decode('utf-8-sig'))
                if 'speaking' in event:
                    self.speaking = bool(event['speaking'])
        except (ValueError, OSError):
            self.error = 'Speech status stream unavailable'
        finally:
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
        kokoro_task = self.kokoro_task
        if kokoro_task and kokoro_task is not asyncio.current_task():
            kokoro_task.cancel()
            await asyncio.gather(kokoro_task, return_exceptions=True)
        self.kokoro_task = None
        process = self.kokoro_process
        if process and process.returncode is None and kokoro_task:
            process.kill()
            await process.wait()
            self.kokoro_process = None
        self.speaking = False
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
        # A full voice shutdown also releases the idle warm Kokoro worker.
        if self.kokoro_process and self.kokoro_process.returncode is None:
            self.kokoro_process.kill()
            await self.kokoro_process.wait()
        self.kokoro_process = None
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
        if self.listener and self.listener.returncode is None:
            self.listener.kill()
            await self.listener.wait()
        if self.reader and self.reader is not asyncio.current_task():
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
        self.listener = None

