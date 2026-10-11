"""Hosted Groq chat model with streamed text and local, permission-checked tool calls."""
import json

import httpx

from .brain import Decision, JuneBrain


class GroqBrain(JuneBrain):
    external = True
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, config, vault):
        self.config = config
        self.vault = vault
        self.status = "configured_unverified"
        self.usage = {}

    @staticmethod
    def _messages(context):
        messages = []
        for item in context:
            if item.get("type") == "function_call":
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": item["call_id"],
                        "type": "function",
                        "function": {
                            "name": item["name"],
                            "arguments": item["arguments"],
                        },
                    }],
                })
            elif item.get("type") == "function_call_output":
                messages.append({
                    "role": "tool",
                    "tool_call_id": item["call_id"],
                    "content": str(item["output"]),
                })
            elif "role" in item:
                content = item.get("content", "")
                if isinstance(content, list):
                    parts = []
                    for part in content:
                        if part.get("type") in ("input_text", "text"):
                            parts.append({"type": "text", "text": part["text"]})
                        elif part.get("type") in ("input_image", "image_url"):
                            parts.append({
                                "type": "image_url",
                                "image_url": {"url": part["image_url"] if isinstance(part["image_url"], str) else part["image_url"]["url"]},
                            })
                    content = parts
                messages.append({"role": item["role"], "content": content})
        return messages

    async def respond(self, context, tools):
        return await self.respond_stream(context, tools)

    async def respond_stream(self, context, tools, on_text=None):
        key = self.vault.get("GROQ_API_KEY")
        if not key:
            self.status = "not_configured"
            raise RuntimeError("Groq API key is not configured. Use June vault to save GROQ_API_KEY.")

        payload = {
            "model": self.config.groq_model,
            "messages": self._messages(context),
            "stream": True,
            "max_completion_tokens": 1024,
            "reasoning_effort": "none",
            "reasoning_format": "hidden",
        }
        if tools:
            payload["tools"] = [{
                "type": "function",
                "function": {k: v for k, v in tool.items() if k not in ("type", "strict")},
            } for tool in tools]

        text_parts = []
        pending_calls = {}
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10)) as client:
                async with client.stream(
                    "POST", self.endpoint,
                    headers={"Authorization": "Bearer " + key},
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        self.status = "error:http_" + str(response.status_code)
                        raise RuntimeError(
                            f"Groq returned HTTP {response.status_code}. "
                            "Check your API key, model access, and rate limits."
                        )
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = event.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        fragment = delta.get("content")
                        if isinstance(fragment, str) and fragment:
                            text_parts.append(fragment)
                            if on_text:
                                await on_text(fragment)
                        for tool in delta.get("tool_calls") or []:
                            index = tool.get("index", 0)
                            pending = pending_calls.setdefault(
                                index, {"id": "", "name": "", "arguments": ""}
                            )
                            if tool.get("id"):
                                pending["id"] = tool["id"]
                            function = tool.get("function") or {}
                            pending["name"] += function.get("name") or ""
                            pending["arguments"] += function.get("arguments") or ""
        except httpx.HTTPError as exc:
            self.status = "unavailable"
            raise RuntimeError("Could not connect to Groq. Check the internet connection.") from exc

        calls, raw = [], []
        for index in sorted(pending_calls):
            item = pending_calls[index]
            if not item["id"] or not item["name"]:
                raise RuntimeError("Groq sent an incomplete tool call.")
            try:
                args = json.loads(item["arguments"] or "{}")
            except json.JSONDecodeError as exc:
                raise RuntimeError("Groq generated invalid tool arguments.") from exc
            if not isinstance(args, dict):
                raise RuntimeError("Groq tool arguments must be a JSON object.")
            calls.append({"id": item["id"], "name": item["name"], "arguments": args})
            raw.append({
                "type": "function_call",
                "call_id": item["id"],
                "name": item["name"],
                "arguments": json.dumps(args),
            })
        self.status = "verified"
        return Decision("".join(text_parts), calls, raw)
