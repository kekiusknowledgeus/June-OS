# Native June V0 and optional local inference

June V0 is June OS's **default AI brain**. It loads an independently trained
10.75-million-parameter character-level Transformer from
`models/june/checkpoints/june_v0_10m.pt`. The model was trained on Tiny
Shakespeare and is an experimental text generator—not a conversational,
tool-using assistant. It cannot reliably understand requests or analyze images.

See [June V0 setup](june-v0.md) for checkpoint placement, PyTorch installation,
and local CPU generation. The default backend needs **no third-party AI API**.

June's identity, memory, tasks, events, tools, permissions, and interfaces are
host-owned. This remains true even when the native brain cannot follow
instructions. Gemini support was removed.

For a separately installed model with sufficient tool-use capabilities, the
existing optional OpenAI-compatible local-server adapter can be enabled with:

```json
{
  "provider": "local",
  "local_url": "http://127.0.0.1:11434/v1",
  "local_model": "your-installed-model"
}
```

Preserve the other local config fields. The endpoint must be loopback HTTP and
implement `/chat/completions`. Do **not** point this adapter at June V0's raw
`.pt` checkpoint: it is not a compatible chat server and cannot reliably emit
structured tool calls. Switching providers does not change the host's permission
policy or migrate memory records.

Speech and durable memory run locally independently of inference. Research and
external services may still require networking when requested. Never assume
the native model has image-understanding or tool abilities simply because the
host application has those integrations.

`models/june/` holds checkpoints and future training artifacts outside Git.
`NeuralInspector` does not fabricate unavailable neural internals.
