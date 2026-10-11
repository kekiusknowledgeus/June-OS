# June V0 (10.75M) — experimental native model

June V0 is a character-level decoder-only Transformer trained from randomly
initialized weights on Tiny Shakespeare. It is not an instruction model,
cannot answer factual questions reliably, call tools or interpret images.
This integration deliberately produces zero tool calls.

June V0 is now the default inference backend. Memory, voice, permissions, and desktop interface are retained. The model checkpoint is deliberately **not** stored on GitHub.

## Try it on Windows

1. Get the changes from this branch onto your laptop.
2. Place your trained checkpoint at:
   `D:\June-V0-Test\models\june\checkpoints\june_v0_10m.pt`
3. Install PyTorch into June's virtual environment:

   ```powershell
   cd D:\June-V0-Test
   .\.venv\Scripts\python.exe -m pip install "torch>=2.5"
   ```

4. Stop any conflicting experiments, then try generation:

   ```powershell
   .\.venv\Scripts\python.exe -m june v0 --prompt "ROMEO:" --tokens 80
   ```

This generates text locally on CPU. It does not require an external API.

## June OS desktop

Stop June and make sure this checkout's `config.json` uses
`"provider": "june_v0"`. Old `"provider": "gemini"` configuration is
automatically migrated when June starts using these changes.

Start June normally. June V0's generative responses will generally be
nonsensical because the model was trained only on Tiny Shakespeare.
June V0 cannot choose or execute tools; known host-side commands may
still work without inference. It does not support images.

Gemini's provider implementation has been removed from June OS.
The separately supported OpenAI and generic local endpoints are
still available as optional provider implementations, but are not
used by default. No AI API key is required for June V0.

The experimental model is loaded lazily, on CPU. Training requires separate
code and compute. PyTorch is an optional dependency, but is required
to use the default June V0 brain for text generation.
