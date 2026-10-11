# June-OS

Windows personal agent with host-enforced permissions, local project tools,
Groq/local inference adapters and a separate experimental June V0 model.

From this checkout:

```powershell
.\.venv\Scripts\python.exe -m june desktop --root D:\June-V0-Test
```

Runtime configuration, credentials, recordings and model weights are local and
excluded from Git. Existing provider settings are preserved. June V0 is a
text-generation experiment, not a tool-capable assistant.

Settings offers Windows SAPI (default, low latency), Kokoro, or automatic
Kokoro with Windows fallback. See [speech configuration](docs/voice.md).

Offline verification:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --test tests/browser_bridge.test.cjs
```

See the [development audit](docs/development-audit-2026-10-11.md) for fixes,
performance measurements, pending live checks and known limitations.
