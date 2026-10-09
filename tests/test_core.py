import pytest
from june.config import Config
from june.store import Store
from june.memory import Memory
from june.security import Vault, Paths, Policy, Risk
from june.tools import FileTools, Registry


@pytest.fixture
def config(tmp_path):
    return Config.load(tmp_path)


def test_memory_persistence_semantics_dedup(config):
    path = config.root / "data/test.db"
    s = Store(path)
    m = Memory(s)
    a = m.remember("Flying humanoid wireless power experiment", explicit=True)
    assert m.remember("flying humanoid wireless power experiment")["id"] == a["id"]
    m.remember("Pasta recipe")
    assert m.search("robot airborne charging")[0]["id"] == a["id"]
    s.close()
    s = Store(path)
    assert len(s.list("memory")) == 2
    s.close()


@pytest.mark.parametrize("path", ["../../escape", ".env", ".git/config", "data/june.db"])
def test_protected_paths(config, path):
    with pytest.raises(PermissionError):
        Paths(config).resolve(path)


async def test_file_concurrent_edit_protection(config):
    f = FileTools(config)
    await f.write("hello.py", "print('hello')")
    old = await f.read("hello.py")
    with pytest.raises(ValueError):
        await f.write("hello.py", "bad")
    await f.write("hello.py", "print('new')", old["sha256"])
    with pytest.raises(ValueError):
        await f.write("hello.py", "stale", old["sha256"])
    with pytest.raises(ValueError):
        await f.delete(".")


def test_redact(config, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "my-private-value")
    assert "my-private-value" not in Vault(config.root).redact("hello my-private-value")


def test_registry_and_policy(config):
    r = Registry()
    FileTools(config).register(r)
    assert Policy(config).check(r.get("file.write"))
    assert not Policy(config).check(r.get("file.read"))
    assert r.get("file__read").name == "file.read"
