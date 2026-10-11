"""Hosted Groq chat model with streamed text and local, permission-checked tool calls."""
import json
import math
import time
from email.utils import parsedate_to_datetime

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
        self.retry_at = 0
        self._client = None

    @staticmethod
    def _messages(context):
        messages = []
        for item in context:
            if item.get("type") == "function_call":
                call_message = {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": item["call_id"],
                        "type": "function",
                        "function": {
                            "name": item["name"],
                            "arguments": item["arguments"],
                        },
                    }],
                }
                if messages and messages[-1].get("tool_calls"):
                    messages[-1]["tool_calls"].extend(call_message["tool_calls"])
                else:
                    messages.append(call_message)
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
        if not any(term in prompt for term in action_terms) and not any(m.get("type") == "function_call_output" for m in context):
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
            add("browser__personal__activate", "browser__personal__navigate",
                "browser__personal__scroll", "browser__personal__media")
        if desktop_intent:
            add("app__open", "path__open", "windows__observe",
                "window__focus", "screen__capture", "vision__analyze", "windows__action")
        if memory_intent:
            add("memory__search", "memory__remember", "records__list",
                "attention__briefing", "schedule__create")
        if not requested:
            add("context__current", "attention__briefing", "file__list",
                "file__read", "project__list", "app__open", "web__search")
        # A small payload keeps cloud latency and request-size limits down.
        # Never starve later capability groups in a mixed-domain request.
        return [available[name] for name in requested]

    async def respond(self, context, tools):
        return await self.respond_stream(context, tools)

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def check_available(self):
        seconds = math.ceil(self.retry_at - time.monotonic())
        if seconds > 0:
            raise BrainUnavailable(f"Groq is cooling down. Retry in {seconds} seconds.", retry_after=seconds)

    @staticmethod
    def retry_seconds(value):
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            try:
                seconds = parsedate_to_datetime(value).timestamp() - time.time()
            except (TypeError, ValueError, OverflowError):
                seconds = 1
        if not math.isfinite(seconds):
            seconds = 1
        return max(1, min(86400, math.ceil(seconds)))

    async def respond_stream(self, context, tools, on_text=None):
        self.check_available()
        self.usage = {}
        key = self.vault.get("GROQ_API_KEY")
        if not key:
            self.status = "not_configured"
            raise BrainUnavailable("Groq API key is not configured. Use June vault to save GROQ_API_KEY.")
        payload = {
            "model": self.config.groq_model,
            "messages": self._messages(context),
            "stream": True,
            "max_completion_tokens": 1024,
        }
        # Reasoning options are model-specific; do not impose Qwen options on
        # every configured model (several models reject them with HTTP 400).
        selected_tools = self._select_tools(context, tools)
        if selected_tools:
            payload["tools"] = [{
                "type": "function",
                "function": {k: v for k, v in tool.items() if k not in ("type", "strict")},
            } for tool in selected_tools]
        text_parts, pending_calls = [], {}
        finished = None
        done = False
        self.status = "requesting"
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(90, connect=10), trust_env=False)
        try:
            async with self._client.stream(
                "POST", self.endpoint,
                headers={"Authorization": "Bearer " + key}, json=payload,
            ) as response:
                if response.status_code >= 400:
                    self.status = "error:http_" + str(response.status_code)
                    if response.status_code == 429:
                        seconds = self.retry_seconds(response.headers.get("retry-after"))
                        self.retry_at = time.monotonic() + seconds
                        raise BrainUnavailable(
                            f"Groq rate limit reached (HTTP 429). Retry in {seconds} seconds. "
                            "Task paused; earlier actions remain recorded and must be reviewed before resuming.",
                            retry_after=seconds,
                        )
                    if response.status_code in {408, 500, 502, 503, 504}:
                        raise ConnectionError(f"Groq temporarily unavailable (HTTP {response.status_code}).")
                    raise BrainUnavailable(f"Groq returned HTTP {response.status_code}. Check model access and request size/format.")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        done = True
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        raise BrainUnavailable("Groq sent malformed stream data; no generated tools were executed.") from None
                    if not isinstance(event, dict) or event.get("error"):
                        raise BrainUnavailable("Groq stream reported an error.")
                    usage = event.get("usage") or (event.get("x_groq") or {}).get("usage")
                    if isinstance(usage, dict):
                        self.usage = {k: v for k, v in usage.items() if isinstance(v, (int, float))}
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    if choice.get("finish_reason"):
                        finished = choice["finish_reason"]
                    delta = choice.get("delta") or {}
                    fragment = delta.get("content")
                    if isinstance(fragment, str) and fragment:
                        text_parts.append(fragment)
                        if sum(map(len, text_parts)) > 64000:
                            raise BrainUnavailable("Groq response exceeded the output budget.")
                        if on_text:
                            await on_text(fragment)
                    for tool in delta.get("tool_calls") or []:
                        index = tool.get("index", 0)
                        if type(index) is not int or not 0 <= index < 8:
                            raise BrainUnavailable("Groq exceeded the tool-call budget.")
                        pending = pending_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                        if tool.get("id"):
                            pending["id"] = tool["id"]
                        function = tool.get("function") or {}
                        pending["name"] += function.get("name") or ""
                        pending["arguments"] += function.get("arguments") or ""
                        if len(pending["arguments"]) > 64000:
                            raise BrainUnavailable("Groq tool arguments exceeded the budget.")
        except httpx.TransportError:
            self.status = "unavailable"
            if text_parts or pending_calls:
                raise BrainUnavailable("Groq stream interrupted. Partial response discarded; no generated tools executed.") from None
            # Runtime owns the bounded retry and counts each request in its budget.
            raise ConnectionError("Could not connect to Groq.") from None
        except (TypeError, AttributeError, KeyError, IndexError):
            self.status = 'invalid_response'
            raise BrainUnavailable('Groq returned malformed response fields; no generated tools executed.') from None
        except BaseException:
            if self.status == "requesting":
                self.status = "unavailable"
            raise

        if not done or finished not in {"stop", "tool_calls"}:
            self.status = "incomplete"
            raise BrainUnavailable("Groq response was incomplete or truncated; no generated tools executed.")
        calls, raw = [], []
        allowed = {t["name"] for t in selected_tools}
        ids = set()
        for index in sorted(pending_calls):
            item = pending_calls[index]
            if not item["id"] or item["id"] in ids or item["name"] not in allowed:
                self.status = "invalid_tool_call"
                raise BrainUnavailable("Groq sent an unknown, duplicate, or incomplete tool call.")
            ids.add(item["id"])
            try:
                args = json.loads(item["arguments"] or "{}")
            except json.JSONDecodeError:
                raise BrainUnavailable("Groq generated invalid tool arguments.") from None
            if not isinstance(args, dict):
                raise BrainUnavailable("Groq tool arguments must be a JSON object.")
            calls.append({"id": item["id"], "name": item["name"], "arguments": args})
            raw.append({"type": "function_call", "call_id": item["id"], "name": item["name"], "arguments": json.dumps(args)})
        if (finished == "tool_calls") != bool(calls) or (not calls and not "".join(text_parts).strip()):
            self.status = "incomplete"
            raise BrainUnavailable("Groq returned an empty or inconsistent response.")
        self.status = "verified"
        return Decision("".join(text_parts), calls, raw)
