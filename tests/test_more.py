import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock
import pytest
from june.config import Config
from june.runtime import Runtime
from june.brain import JuneBrain, Decision, LocalJuneBrain
from june.instance import InstanceLock


class Brain(JuneBrain):
    async def respond(self, context, tools):
        return Decision("Observed")


async def test_single_runtime_lock(tmp_path):
    config = Config.load(tmp_path)
    r1, r2 = Runtime(config, Brain()), Runtime(config, Brain())
    await r1.start()
    with pytest.raises(RuntimeError, match="already running"):
        await r2.start()
    await r2.close()
    await r1.close()


async def test_local_model_must_be_local(tmp_path):
    config = Config.load(tmp_path)
    config.local_url = "https://attacker.invalid/v1"
    with pytest.raises(ValueError):
        LocalJuneBrain(config)


async def test_scheduled_agent_job_and_quiet(tmp_path):
    r = Runtime(Config.load(tmp_path), Brain())
    due = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    await r.schedule("Local briefing", due, prompt="Summarize pending tasks")
    await r.scheduler.tick()
    await asyncio.gather(*list(r.jobs.values()))
    assert r.store.list("job")[0]["status"] == "completed"
    await r.scheduler.tick()
    assert len(r.store.list("job")) == 1
    r.config.quiet = True
    assert (await r.notifications.notify("Quiet", "Do not deliver"))["status"] == "suppressed"
    await r.close()


async def test_watcher_records_real_change(tmp_path):
    r = Runtime(Config.load(tmp_path), Brain())
    path = tmp_path / "watched.txt"
    path.write_text("one")
    await r.watch("file", str(path))
    await r.watcher.tick()
    path.write_text("two")
    import os
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
    await r.watcher.tick()
    assert r.store.list("event")[0]["type"] == "file_changed"
    await r.close()


async def test_voice_stop_and_privacy_command(tmp_path):
    r = Runtime(Config.load(tmp_path), Brain())
    r.cancel_all = AsyncMock()
    r.voice.stop_speaking = AsyncMock()
    await r.on_voice("June stop")
    r.cancel_all.assert_awaited()
    r.voice.stop_speaking.assert_awaited()
    await r.on_voice("June privacy mode")
    assert r.config.privacy and not r.config.voice_enabled
    await r.close()


async def test_model_transport_retry_is_bounded(tmp_path):
    import httpx
    brain = Brain()
    brain.respond = AsyncMock(side_effect=[httpx.ConnectError("offline"), Decision("Recovered")])
    r = Runtime(Config.load(tmp_path), brain)
    job = r.submit("Hello")
    await r.jobs[job["id"]]
    assert r.store.get("job", job["id"])["response"] == "Recovered"
    assert brain.respond.await_count == 2
    await r.close()


async def test_newest_context_and_secret_redaction(tmp_path):
    r = Runtime(Config.load(tmp_path), Brain())
    r.vault.values["SAMPLE_TOKEN"] = "sensitive-example-123"
    for i in range(20):
        r.store.put("message", {"role": "user", "content": str(i), "session": "test"})
    context = r.context("sensitive-example-123", "test")
    assert any(x.get("content") == "19" for x in context)
    assert not any(x.get("content") == "0" for x in context)
    assert "sensitive-example-123" not in str(context)
    await r.close()


async def test_task_updates_preserve_fields_and_reject_cycles(tmp_path):
    r = Runtime(Config.load(tmp_path), Brain())
    a = await r.task_save("A", description="Keep this", priority=1, project="Galileo")
    b = await r.task_save("B", dependencies=[a["id"]])
    with pytest.raises(ValueError, match="Cyclic"):
        await r.task_save("A", id=a["id"], dependencies=[b["id"]])
    updated = await r.task_save("A", id=a["id"], status="done")
    assert updated["description"] == "Keep this" and updated["project"] == "Galileo" and updated["priority"] == 1
    await r.close()
