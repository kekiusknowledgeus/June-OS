"""Hosted Groq chat model with streamed text and local, permission-checked tool calls."""
import json

import httpx

from .brain import Decision, JuneBrain
from .errors import BrainUnavailable


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

    @staticmethod
    def _select_tools(context, tools):
        """Send only task-relevant tools, rather than June's entire tool catalog."""
        if not tools:
            return []
        prompt = next(
            (m["content"] for m in reversed(context)
             if m.get("role") == "user"
             and isinstance(m.get("content"), str)
             and not m["content"].startswith("Host verification gate:")),
            "",
        ).lower()
        action_terms = (
            "open", "launch", "start", "run", "execute", "create", "write",
            "edit", "change", "fix", "debug", "test", "build", "file",
            "folder", "project", "code", "python", "javascript", "git",
            "search", "research", "browse", "website", "web", "url",
            "send", "message", "whatsapp", "reply", "chat",
            "read", "inspect", "check", "list", "find", "show",
            "window", "screen", "app", "click", "type", "computer",
            "copy", "move", "delete", "rename", "remember", "memory",
            "task", "schedule", "remind", "status", "summarize",
        )
        # No tool definitions needed for greetings and simple conversation.
        if not any(term in prompt for term in action_terms):
            return []

        available = {t["name"]: t for t in tools}
        requested = []
        def add(*names):
            for name in names:
                if name in available and name not in requested:
                    requested.append(name)

        file_intent = any(s in prompt for s in (
            "file", "folder", "directory", "document", "write", "edit",
            "save", "copy", "move", "delete", "rename", "code", "python",
            "javascript", "script", "bug", "debug", "fix", "project",
        ))
        coding_intent = any(s in prompt for s in (
            "code", "python", "javascript", "script", "bug", "debug",
            "fix", "project", "test", "build", "git", "run", "execute",
        ))
        browser_intent = any(s in prompt for s in (
            "web", "browser", "research", "website", "url", "google",
            "youtube", "search online", "internet", "tab", "page",
            "whatsapp", "spotify", "send message", "send a", "message",
        ))
        desktop_intent = any(s in prompt for s in (
            "app", "notepad", "calculator", "explorer", "vs code",
            "vscode", "window", "screen", "click", "open", "launch",
            "computer", "desktop",
        ))
        memory_intent = any(s in prompt for s in (
            "memory", "remember", "recall", "task", "schedule", "remind",
            "attention", "today", "status",
        ))

        if coding_intent:
            add("project__list", "project__inspect", "project__detect",
                "project__switch", "file__list", "file__read",
                "file__search", "file__metadata", "file__create",
                "file__edit", "file__write", "file__mkdir",
                "git__inspect", "shell__run", "project__run")
        elif file_intent:
            add("file__list", "file__read", "file__search",
                "file__metadata", "file__create", "file__edit",
                "file__write", "file__mkdir", "path__open")

        if browser_intent:
            add("web__search", "web__read", "browser__personal__search",
                "browser__personal__open", "browser__personal__active_tab",
                "browser__personal__read", "browser__personal__list_tabs")
            if any(term in prompt for term in ("send", "message", "reply", "type", "click", "fill", "whatsapp")):
                add("browser__personal__type", "browser__personal__click",
                    "browser__personal__focus", "browser__personal__submit")
        if desktop_intent:
            add("app__open", "path__open", "windows__observe",
                "window__focus", "screen__capture", "windows__action")
        if memory_intent:
            add("memory__search", "memory__remember", "records__list",
                "attention__briefing", "schedule__create")
        if not requested:
            add("context__current", "attention__briefing", "file__list",
                "file__read", "project__list", "app__open", "web__search")
        # A small payload keeps cloud latency and request-size limits down.
        return [available[name] for name in requested[:18]]

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
        selected_tools = self._select_tools(context, tools)
        if selected_tools:
            payload["tools"] = [{
                "type": "function",
                "function": {k: v for k, v in tool.items() if k not in ("type", "strict")},
            } for tool in selected_tools]

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
                        if response.status_code == 429:
                            # Do not keep retrying a rate-limited provider. Expose
                            # only timing/limit metadata, never credentials or prompts.
                            retry_header = response.headers.get("retry-after", "")
                            try:
                                seconds = max(0, min(86400, int(float(retry_header))))
                            except (TypeError, ValueError, OverflowError):
                                seconds = 0
                            wait = f" Retry after approximately {seconds} seconds." if seconds else " Check your rate-limit reset time."
                            raise BrainUnavailable(
                                "Groq rate limit reached (HTTP 429)." + wait
                                + " June has paused this cloud task; no action was executed.",
                                retry_after=seconds,
                            )
                        if response.status_code == 413:
                            size = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
                            raise RuntimeError(
                                f"Groq HTTP 413: request too large "
                                f"({size // 1024} KiB, {len(selected_tools)} tools). "
                                "Try a shorter conversation or reduce available tools."
                            )
                        raise RuntimeError(
                            f"Groq returned HTTP {response.status_code}. "
                            "Check model access, request format, and rate limits."
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
