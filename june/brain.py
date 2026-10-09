from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import httpx


@dataclass
class Decision:
    text: str = ""
    calls: list[dict] = field(default_factory=list)
    raw: list[dict] = field(default_factory=list)


class JuneBrain(ABC):
    external = False

    @abstractmethod
    async def respond(self, context, tools) -> Decision: ...

    async def respond_stream(self, context, tools, on_text=None):
        decision = await self.respond(context, tools)
        if on_text and decision.text:
            await on_text(decision.text)
        return decision

    async def reason(self, context):
        return await self.respond(context, [])

    async def plan(self, context):
        return await self.respond(context + [{"role": "user", "content": "Form a concise plan grounded in observed facts."}], [])

    async def choose_tools(self, context, tools):
        return await self.respond(context, tools)

    async def interpret_observation(self, context):
        return await self.reason(context)

    async def extract_memory(self, context):
        return await self.respond(context + [{"role": "user", "content": "Extract only durable memory candidates as JSON with text, category, confidence. Mark inferences. Return [] if none."}], [])

    async def summarize(self, context):
        return await self.respond(context + [{"role": "user", "content": "Summarize the established facts concisely."}], [])

    async def analyze_image(self, question, data_url):
        return await self.respond([{"role": "user", "content": [{"type": "input_text", "text": question}, {"type": "input_image", "image_url": data_url}]}], [])

    async def process_audio(self, audio):
        raise RuntimeError("Use the configured SpeechProvider for audio transcription")


class OpenAIBrain(JuneBrain):
    external = True

    def __init__(self, config, vault):
        self.config, self.vault = config, vault
        self.status = "configured_unverified"

    async def respond(self, context, tools):
        key = self.vault.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OpenAI is not configured")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {key}"}, json={"model": self.config.model, "input": context, "tools": tools, "store": False, "max_output_tokens": 3000})
            if response.status_code != 200:
                try:
                    code = str(response.json().get("error", {}).get("code") or "unknown")
                except (ValueError, AttributeError):
                    code = "unknown"
                code = code if code.replace("_", "").isalnum() else "unknown"
                self.status = "error:" + code
                raise RuntimeError(f"OpenAI request failed: HTTP {response.status_code}, code={code}")
            data = response.json()
            self.status = "verified"
        calls, texts = [], []
        for item in data.get("output", []):
            if item["type"] == "function_call":
                calls.append({"id": item["call_id"], "name": item["name"], "arguments": json.loads(item["arguments"])})
            elif item["type"] == "message":
                texts += [c.get("text", "") for c in item.get("content", []) if c["type"] == "output_text"]
        return Decision("\n".join(texts), calls, data.get("output", []))


class LocalJuneBrain(JuneBrain):
    """Local OpenAI-compatible chat endpoint; no API key or hosted inference needed."""
    def __init__(self, config):
        self.config = config
        from urllib.parse import urlparse
        parsed = urlparse(config.local_url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Local brain endpoint must be loopback HTTP")

    async def respond(self, context, tools):
        if not self.config.local_model:
            raise RuntimeError("Local model is not configured")
        messages = []
        for item in context:
            if item.get("type") == "function_call":
                messages.append({"role": "assistant", "tool_calls": [{"id": item["call_id"], "type": "function", "function": {"name": item["name"], "arguments": item["arguments"]}}]})
            elif item.get("type") == "function_call_output":
                messages.append({"role": "tool", "tool_call_id": item["call_id"], "content": item["output"]})
            elif "role" in item:
                content = item.get("content", "")
                if isinstance(content, list):
                    content = [{"type": "text", "text": c["text"]} if c["type"] == "input_text" else {"type": "image_url", "image_url": {"url": c["image_url"]}} for c in content]
                messages.append({"role": item["role"], "content": content})
        payload = {"model": self.config.local_model, "messages": messages, "stream": False}
        if tools:
            payload["tools"] = [{"type": "function", "function": {k: v for k, v in t.items() if k not in {"type", "strict"}}} for t in tools]
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(self.config.local_url.rstrip("/") + "/chat/completions", json=payload)
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
        raw, calls = [], []
        for c in msg.get("tool_calls", []):
            f = c["function"]
            args = f["arguments"] if isinstance(f["arguments"], str) else json.dumps(f["arguments"])
            raw.append({"type": "function_call", "call_id": c["id"], "name": f["name"], "arguments": args})
            calls.append({"id": c["id"], "name": f["name"], "arguments": json.loads(args)})
        return Decision(msg.get("content") or "", calls, raw)


BrainProvider = JuneBrain
VisionProvider = JuneBrain
