"""Small, optional CPU tests for June V0's checkpoint adapter."""
import pytest
from june.config import Config
from june.v0_brain import JuneV0Brain


def test_missing_checkpoint(tmp_path):
    brain = JuneV0Brain(Config.load(tmp_path))
    assert brain.status == "not_configured"
    with pytest.raises(FileNotFoundError, match="checkpoint missing"):
        brain.sample()


@pytest.mark.asyncio
async def test_v0_refuses_images(tmp_path):
    brain = JuneV0Brain(Config.load(tmp_path))
    with pytest.raises(NotImplementedError, match="text-only"):
        await brain.analyze_image("Describe it", "data:image/png;base64,AA==")


@pytest.mark.asyncio
async def test_v0_tiny_checkpoint_no_tool_calls(tmp_path):
    torch = pytest.importorskip("torch")
    from june.v0_model import JuneV0

    cfg = Config.load(tmp_path)
    model = JuneV0(vocab_size=4, block_size=8, d_model=12,
                   n_head=3, n_layer=1, dropout=0.0)
    checkpoint = {
        "config": {"vocab_size": 4, "block_size": 8, "d_model": 12,
                   "n_head": 3, "n_layer": 1, "dropout": 0.0},
        "vocab_chars": list("AB \n"),
        "model_state_dict": model.state_dict(),
        "steps_completed": 1,
    }
    path = cfg.root / "models/june/checkpoints/june_v0_10m.pt"
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, path)

    brain = JuneV0Brain(cfg)
    generated = brain.sample("AB! xyz", 4)
    assert len(generated) == 4
    assert set(generated) <= set("AB \n")
    decision = await brain.respond(
        [{"role": "user", "content": "AB"}],
        [{"name": "shell.run"}],
    )
    assert "experimental character generation" in decision.text
    assert decision.calls == []
    assert decision.raw == []
    assert brain.status == "loaded"
