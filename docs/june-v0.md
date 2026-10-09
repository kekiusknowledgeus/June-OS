# June V0 (10.75M) — experimental native model

June V0 is a character-level decoder-only Transformer trained from randomly
initialized weights on Tiny Shakespeare. It is not an instruction model,
cannot answer factual questions reliably, call tools or interpret images.
This integration deliberately produces zero tool calls.

Your existing Gemini backend, memory, voice, permissions, and desktop interface
stay unchanged. The model checkpoint is deliberately **not** stored on GitHub.

## Try it on Windows without changing the normal June backend

1. Get the changes from this branch onto your laptop.
2. Place your trained checkpoint at:
   `D:\June\models\june\checkpoints\june_v0_10m.pt`
3. Install PyTorch into June's virtual environment:

   ```powershell
   cd D:\June
   .\.venv\Scripts\python.exe -m pip install "torch>=2.5"
   ```

4. Stop any conflicting experiments, then try generation:

   ```powershell
   .\.venv\Scripts\python.exe -m june v0 --prompt "ROMEO:" --tokens 80
   ```

This generates text locally on CPU. It does not require an external API.

## Optional temporary desktop experiment

Leave `"provider": "gemini"` in `config.json` for ordinary work.
To use V0 in June's existing UI, **stop June**, change the provider in your
local config to `"june_v0"`, then restart. The generated text will usually
be nonsensical. June V0 cannot select or execute tools; known host-side
commands may still work without it. Restore `"provider": "gemini"` after
testing. Do not modify or commit credentials.

The experimental model is loaded lazily, on CPU. Training requires separate
code and compute. PyTorch is an optional dependency, so normal June installs
do not need to install it.
