import asyncio
import json
import sys
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from june.config import Config
from june.security import Paths, Vault
from june.tools import Registry, FileTools, run_process
from june.webtools import public_url, Browser
from june.brain import OpenAIBrain, LocalJuneBrain
from june.runtime import Runtime
from june.camera import Camera


@pytest.fixture
def config(tmp_path):
    return Config.load(tmp_path)


async def test_shell_result_timeout_and_cancel(config):
    result = await run_process([sys.executable, "-c", "import sys; print('out'); print('err',file=sys.stderr); sys.exit(3)"], config.root)
    assert result["returncode"] == 3 and "out" in result["stdout"] and "err" in result["stderr"]
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        await run_process([sys.executable, "-c", "import time;time.sleep(60)"], config.root, timeout=1)
    assert time.monotonic() - start < 5
    task = asyncio.create_task(run_process([sys.executable, "-c", "import time;time.sleep(60)"], config.root))
    await asyncio.sleep(.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_large_binary_and_invalid_arguments(config):
    f = FileTools(config)
    (config.root / "large.txt").write_bytes(b"x" * (config.max_file_bytes + 1))
    (config.root / "binary.dat").write_bytes(b"a\0b")
    for name in ["large.txt", "binary.dat"]:
        with pytest.raises(ValueError):
            await f.read(name)
    registry = Registry()
    f.register(registry)
    with pytest.raises(ValueError):
        await registry.execute("file.read", {"path": ["test"]})
    with pytest.raises(ValueError):
        await registry.execute("file.read", {"path": "x", "approved": True})


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://169.254.169.254/", "http://[::1]/", "file:///C:/secrets", "https://user:password@example.com/", "http://localhost:9999/"])
async def test_ssrf_blocked(url):
    with pytest.raises(PermissionError):
        await public_url(url)


async def test_screen_and_camera_disabled(config):
    from june.windows import Windows
    with pytest.raises(PermissionError):
        await Windows(config).capture()
    with pytest.raises(PermissionError):
        await Camera(config).capture()


async def test_gui_changed_window_never_clicks(config, monkeypatch):
    from june.windows import Windows
    config.screen_enabled = True
    windows = Windows(config)
    monkeypatch.setattr(windows, "capture", AsyncMock(return_value={"window": {"title": "Different"}}))
    with pytest.raises(ValueError):
        await windows.action("click", expected_window="Expected")


async def test_brain_contract_and_tool_parsing(config, monkeypatch):
    import httpx
    vault = Vault(config.root)
    vault.values["OPENAI_API_KEY"] = "test-not-real"
    response = httpx.Response(200, json={"output": [{"type": "function_call", "call_id": "a", "name": "file__list", "arguments": "{}"}, {"type": "message", "content": [{"type": "output_text", "text": "Inspecting"}]}]})
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=response))
    brain = OpenAIBrain(config, vault)
    result = await brain.respond([], [])
    assert result.text == "Inspecting" and result.calls[0]["name"] == "file__list"
    assert brain.status == "verified"
    response = httpx.Response(429, json={"error": {"code": "credit_balance_exhausted"}})
    monkeypatch.setattr(httpx.AsyncClient, "post", AsyncMock(return_value=response))
    with pytest.raises(RuntimeError, match="credit_balance_exhausted"):
        await brain.respond([], [])


async def test_integrations_not_fabricated(config):
    from june.integrations import Integrations
    vault = Vault(config.root)
    vault.get = lambda name: None
    integrations = Integrations(config, vault)
    health = await integrations.health()
    assert all(p["status"] == "not_configured" for p in health.values())
    with pytest.raises(RuntimeError):
        await integrations.execute("github", "repositories", {})


def test_config_restart(config):
    config.privacy = True
    config.save()
    assert Config.load(config.root).privacy


async def test_approval_tamper_rejected(config):
    r = Runtime(config)
    args = {"path": "safe.txt", "text": "ok"}
    t = asyncio.create_task(r.execute("test", "file.write", args))
    for _ in range(100):
        if r.approvals:
            break
        await asyncio.sleep(.01)
    aid = next(iter(r.approvals))
    args["path"] = "different.txt"
    r.approve(aid, True)
    result = await t
    assert result["status"] == "permission_denied"
    assert not (config.root / "different.txt").exists()
    await r.close()
