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

    async def speak(self, text):
        if self.config.privacy or not self.config.voice_enabled:
            return
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

