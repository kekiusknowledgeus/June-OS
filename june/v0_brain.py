"""Experimental, text-only June V0 brain. No reliable tool calling or vision."""
import asyncio
from .brain import JuneBrain, Decision


class JuneV0Brain(JuneBrain):
    external = False
    checkpoint_name = "june_v0_10m.pt"

    def __init__(self, config):
        self.config = config
        self.checkpoint_path = config.root / "models" / "june" / "checkpoints" / self.checkpoint_name
        self.model = None
        self.vocab_chars = None
        self.char_to_id = None
        self.status = "checkpoint_present" if self.checkpoint_path.is_file() else "not_configured"
        self.usage = {}

    def _load(self):
        if self.model is not None:
            return
        if not self.checkpoint_path.is_file():
            raise FileNotFoundError(
                f"June V0 checkpoint missing: {self.checkpoint_path}. "
                "See docs/june-v0.md; Gemini remains available."
            )
        try:
            import torch
            from .v0_model import JuneV0
        except ImportError as exc:
            raise RuntimeError(
                "June V0 requires optional PyTorch. Install it into June's .venv first."
            ) from exc

        # weights_only=True rejects arbitrary object deserialization. Trust the file source.
        checkpoint = torch.load(self.checkpoint_path, map_location="cpu", weights_only=True)
        cfg = checkpoint["config"]
        chars = checkpoint["vocab_chars"]
        if not isinstance(chars, (str, list, tuple)):
            raise ValueError("Invalid June V0 vocabulary")
        if not all(isinstance(ch, str) and len(ch) == 1 for ch in chars):
            raise ValueError("June V0 vocabulary must contain single characters")
        if len(set(chars)) != len(chars) or len(chars) != cfg["vocab_size"]:
            raise ValueError("June V0 checkpoint vocabulary mismatch")
        if not (0 < cfg["block_size"] <= 2048 and 0 < cfg["n_layer"] <= 24
                and 0 < cfg["d_model"] <= 2048 and 0 < cfg["n_head"] <= 32
                and cfg["d_model"] % cfg["n_head"] == 0):
            raise ValueError("Unsupported June V0 checkpoint configuration")
        model = JuneV0(
            cfg["vocab_size"], cfg["block_size"], cfg["d_model"],
            cfg["n_head"], cfg["n_layer"], cfg["dropout"]
        )
        model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        model.eval()
        self.model = model
        self.vocab_chars = list(chars)
        self.char_to_id = {ch: i for i, ch in enumerate(chars)}
        self.status = "loaded"

    def sample(self, prompt="ROMEO:\n", max_new_tokens=64):
        """Generate characters on CPU; never dispatch tools or commands."""
        if not 1 <= max_new_tokens <= 500:
            raise ValueError("Tokens must be between 1 and 500")
        self._load()
        import torch

        # The training notebook's tokenizer only recognizes its character vocabulary.
        seed = "".join(ch for ch in prompt if ch in self.char_to_id)
        seed = seed[-self.model.block_size:]
        if not seed:
            seed = next(iter(self.char_to_id))
        idx = torch.tensor([[self.char_to_id[ch] for ch in seed]], dtype=torch.long)
        with torch.inference_mode():
            output = self.model.generate(idx, max_new_tokens=max_new_tokens)
        new_ids = output[0].tolist()[len(seed):]
        self.usage = {"generated_characters": len(new_ids)}
        return "".join(self.vocab_chars[i] for i in new_ids)

    async def respond(self, context, tools):
        # This educational model has NO reliable instructions, function calling,
        # computer control or vision. Never turn its output into tool requests.
        prompt = next(
            (item["content"] for item in reversed(context)
             if item.get("role") == "user" and isinstance(item.get("content"), str)),
            "ROMEO:\n",
        )
        sample = await asyncio.to_thread(self.sample, prompt, 64)
        return Decision(
            "June V0 experimental character generation (not a factual answer; "
            "no tool use or command execution):\n" + sample
        )

    async def analyze_image(self, question, data_url):
        raise NotImplementedError("June V0 is text-only and cannot analyze images")
