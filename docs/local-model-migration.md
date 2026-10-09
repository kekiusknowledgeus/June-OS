# Removing external inference

June's identity, memory, tasks, events, tools, permissions and interfaces are host-owned. Gemini is the current implementation of `JuneBrain`; OpenAI remains optional. Requests use `store: false`, which is not a promise that no provider-side retention policy applies. See the selected provider's data policy before sending sensitive content.

To use an already installed local model server, stop June and edit `config.json`:

```json
{
  "provider": "local",
  "local_url": "http://127.0.0.1:11434/v1",
  "local_model": "your-installed-model"
}
```

Preserve the other config fields. The endpoint must be loopback HTTP and implement OpenAI-compatible `/chat/completions` tool calling. Install a model with suitable tool-use/context capabilities using your chosen local inference runtime, then restart June and test read-only tools before modifications. Image analysis also requires multimodal support. The machine's model/GPU capacity has not been benchmarked and no model weights have been downloaded.

`LocalJuneBrain` translates provider-independent tool calls/results and images into the compatible chat format. A future native June model can directly implement the abstract brain contract, avoiding even that wire-format compatibility. It must preserve tool-call IDs, return structured decisions, support bounded cancellation/timeouts, and never take over host permission decisions.

Speech currently runs locally through Windows. Memory's LSA/concept retrieval is local. Replace either independently with June models through their provider interfaces. Research and external services remain optional network tools; the local API, records, scheduling and UI do not require the internet.

Gemini 2.5 Flash passed the live transport, coding and research checks. The optional OpenAI adapter's earlier test returned `credit_balance_exhausted`. Switching providers does not migrate local records or change the host permission policy.

`models/june/` contains tokenizer, config, checkpoints, weights, training and telemetry directories as empty future integration locations. `NeuralInspector` defines architecture/layers/parameters/tensors/tokenization/logits/probabilities/attention/activations/training/gradients and runtime metrics. Internal inspection is unavailable for hosted Gemini and for a compatible local endpoint until a real telemetry adapter is connected; a local URL alone never produces fabricated model internals.
