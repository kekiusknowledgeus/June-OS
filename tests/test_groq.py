"""Groq backend tests without network traffic or a real credential."""
import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from june.config import Config
from june.groq_brain import GroqBrain
from june.runtime import Runtime


class FakeVault:
    def get(self, name):
        return "test-only-not-a-real-key" if name == "GROQ_API_KEY" else None


def test_groq_provider_registration(tmp_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-only-not-a-real-key")
    config = Config.load(tmp_path)
    config.provider = "groq"
    runtime = Runtime(config)
    assert isinstance(runtime.brain, GroqBrain)
    assert runtime.brain.external is True
    asyncio.run(runtime.close())


@pytest.mark.asyncio
async def test_missing_key_prevents_request(tmp_path):
    brain = GroqBrain(Config.load(tmp_path), type("Vault", (), {"get": lambda self, key: None})())
    with pytest.raises(RuntimeError, match="not configured"):
        await brain.respond([{"role": "user", "content": "hi"}], [])


@pytest.mark.asyncio
async def test_streamed_text_and_tool_call(tmp_path, monkeypatch):
    captured = []
    class StreamResponse:
        status_code = 200
        async def aiter_lines(self):
            events = [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "file.read", "arguments": '{"path":'}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"notes.txt"}'}}]}}]},
            ]
            for event in events:
                yield "data: " + json.dumps(event)
            yield "data: [DONE]"
    class Context:
        async def __aenter__(self):
            return StreamResponse()
        async def __aexit__(self, *args):
            return False
    class Client:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        def stream(self, method, url, **kwargs):
            assert url.startswith("https://api.groq.com/")
            assert kwargs["json"]["reasoning_effort"] == "none"
            assert kwargs["json"]["stream"] is True
            return Context()
    monkeypatch.setattr("june.groq_brain.httpx.AsyncClient", Client)
    async def collect(chunk):
        captured.append(chunk)
    brain = GroqBrain(Config.load(tmp_path), FakeVault())
    d = await brain.respond_stream(
        [{"role": "user", "content": "read my file"}],
        [{"name": "file.read", "description": "Read file", "parameters": {"type": "object", "properties": {}}}],
        collect,
    )
    assert d.text == "Hello" and captured == ["Hello"]
    assert d.calls == [{"id": "call_1", "name": "file.read", "arguments": {"path": "notes.txt"}}]
    assert d.raw[0]["type"] == "function_call"
