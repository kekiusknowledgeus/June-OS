"""Gemini transport only. All function execution remains in the host runtime."""
import asyncio
import copy
import json
import re
import time
import uuid
import httpx
from .brain import JuneBrain, Decision


class BrainUnavailable(RuntimeError):
    def __init__(self, message, retry_after=0):
        super().__init__(message)
        self.retry_after = retry_after


class GeminiBrain(JuneBrain):
    external = True

    def __init__(self, config, vault):
        self.config, self.vault = config, vault
        self.status = "configured_unverified" if vault.get("GEMINI_API_KEY") else "not_configured"
        self.cooldown_until = 0
        self.last_call = 0
        self.usage = {}
        self.latency_ms = None

    def payload(self, context, tools):
        system, contents, calls, native_ids = [], [], {}, set()
        def append(role, parts):
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": parts})
        for item in context:
            kind = item.get("type")
            if kind == "gemini_content":
                original = copy.deepcopy(item["content"])
                contents.append(original)
                for part in original.get("parts", []):
                    fc = part.get("functionCall")
                    if fc:
                        calls[fc.get("id", fc["name"])] = fc["name"]
                        if fc.get("id"):
                            native_ids.add(fc["id"])
                calls.update(item.get("call_names", {}))
            elif kind == "function_call_output":
                output = item["output"]
                try:
                    output = json.loads(output)
                except (ValueError, TypeError):
                    output = {"result": output}
                name = calls.get(item["call_id"])
                if not name:
                    raise ValueError("Missing Gemini call/result pairing")
                response = {"name": name, "response": output if isinstance(output, dict) else {"result": output}}
                if item["call_id"] in native_ids:
                    response["id"] = item["call_id"]
                append("user", [{"functionResponse": response}])
            elif item.get("role") in {"system", "developer"}:
                system.append(item["content"])
            elif "role" in item:
                content = item.get("content", "")
                parts = []
                if isinstance(content, str):
                    parts = [{"text": content}]
                else:
                    for p in content:
                        if p["type"] == "input_text":
                            parts.append({"text": p["text"]})
                        elif p["type"] == "input_image":
                            prefix, data = p["image_url"].split(",", 1)
                            parts.append({"inlineData": {"mimeType": prefix[5:].split(";")[0], "data": data}})
                append("model" if item["role"] == "assistant" else "user", parts)
        result = {"contents": contents, "generationConfig": {"maxOutputTokens": 4096}, "store": False}
        if system:
            result["systemInstruction"] = {"parts": [{"text": "\n".join(system)}]}
        if tools:
            result["tools"] = [{"functionDeclarations": [{"name": t["name"], "description": t["description"], "parametersJsonSchema": t["parameters"]} for t in tools]}]
        return result

    def decision(self, content):
        calls, text, names = [], [], {}
        for part in content.get("parts", []):
            if part.get("thought"):
                continue  # Never display internal reasoning or thought summaries.
            if "functionCall" in part:
                fc = part["functionCall"]
                id = fc.get("id") or uuid.uuid4().hex
                calls.append({"id": id, "name": fc["name"], "arguments": fc.get("args", {})})
                names[id] = fc["name"]
            elif "text" in part:
                text.append(part["text"])
        # Opaque thought signatures stay on original parts and only round-trip to Gemini.
        return Decision("".join(text), calls, [{"type": "gemini_content", "content": content, "call_names": names}])

    async def respond(self, context, tools):
        return await self.respond_stream(context, tools)

    async def respond_stream(self, context, tools, on_text=None):
        key = self.vault.get("GEMINI_API_KEY")
        if not key:
            self.status = "not_configured"
            raise BrainUnavailable("Brain unavailable: GEMINI_API_KEY is not configured. Local commands still work.")
        if time.time() < self.cooldown_until:
            raise BrainUnavailable("Brain unavailable: Gemini quota cooldown is active.", self.cooldown_until - time.time())
        model = self.config.gemini_model
        if not re.fullmatch(r"[\w.-]+", model):
            raise ValueError("Invalid Gemini model identifier")
        await asyncio.sleep(max(0, self.config.provider_min_interval - (time.monotonic() - self.last_call)))
        self.last_call = time.monotonic()
        started = time.monotonic()
        content = {"role": "model", "parts": []}
        self.usage = {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=15)) as client:
                async with client.stream("POST", f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse", headers={"x-goog-api-key": key}, json=self.payload(context, tools)) as response:
                    if response.status_code != 200:
                        raw = await response.aread()
                        try:
                            code = json.loads(raw).get("error", {}).get("status", "UNKNOWN")
                        except ValueError:
                            code = "UNKNOWN"
                        code = code if re.fullmatch(r"[A-Z_]+", str(code)) else "UNKNOWN"
                        self.status = f"unavailable:{response.status_code}:{code}"
                        if response.status_code == 429:
                            self.cooldown_until = time.time() + 60
                        raise BrainUnavailable(f"Brain unavailable: Gemini HTTP {response.status_code} ({code}). Local commands still work.", 60 if response.status_code == 429 else 0)
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        chunk = json.loads(line[6:])
                        self.usage = chunk.get("usageMetadata", self.usage)
                        candidates = chunk.get("candidates", [])
                        if not candidates:
                            continue
                        parts = candidates[0].get("content", {}).get("parts", [])
                        content["parts"].extend(parts)
                        if on_text:
                            for part in parts:
                                if part.get("text") and not part.get("thought"):
                                    await on_text(part["text"])
                        if candidates[0].get("finishReason") in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"}:
                            raise BrainUnavailable("Gemini could not provide a response for this request.")
            if not content["parts"]:
                raise BrainUnavailable("Brain unavailable: Gemini returned no response.")
            self.status = "verified"
            return self.decision(content)
        except httpx.HTTPError:
            self.status = "unavailable:network"
            raise BrainUnavailable("Brain unavailable: Gemini network connection failed. Local commands still work.") from None
        finally:
            self.latency_ms = round((time.monotonic() - started) * 1000)
