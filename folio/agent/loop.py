from __future__ import annotations

import json
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from folio.agent.prompts import SYSTEM_PROMPT
from folio.config import get_settings
from folio.memory import append_event
from folio.schemas import ChatResponse, Source, ToolTrace
from folio.tools import TOOL_SPECS, run_tool


def _gemini_tools() -> list[types.Tool]:
    declarations = []
    for spec in TOOL_SPECS:
        declarations.append(
            types.FunctionDeclaration(
                name=spec["name"],
                description=spec["description"],
                parameters=spec["parameters"],
            )
        )
    return [types.Tool(function_declarations=declarations)]


def _preview(text: str, limit: int = 400) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _tool_config(mode: str) -> types.ToolConfig:
    return types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(mode=mode)
    )


def _finish(
    reply: str,
    sources: list[Source],
    traces: list[ToolTrace],
    session_id: str,
    path: str,
) -> ChatResponse:
    append_event(
        session_id,
        {
            "type": "assistant",
            "text": reply,
            "sources": [s.model_dump() for s in sources],
            "tool_traces": [t.model_dump() for t in traces],
        },
    )
    indexed = [source.model_copy(update={"index": i}) for i, source in enumerate(sources, start=1)]
    return ChatResponse(
        reply=reply,
        sources=indexed,
        tool_traces=traces,
        session_id=session_id,
    )


def _fallback_from_tools(traces: list[ToolTrace], sources: list[Source]) -> str:
    summaries = [t.result_preview for t in traces if t.result_preview]
    if not summaries:
        return "Research tools returned no usable text. Try again in a moment."
    brief = summaries[-1]
    if len(brief) > 900:
        brief = brief[:899] + "…"
    suffix = (
        " Sources are listed in the dossier."
        if sources
        else " I could not attach source links this time."
    )
    return f"{brief}{suffix}"


async def run_chat(message: str, session_id: str = "default") -> ChatResponse:
    settings = get_settings()
    if not settings.google_api_key:
        return ChatResponse(
            reply=(
                "Google API key is missing. Add GOOGLE_API_KEY to your .env file "
                "so Folio can reason with Gemini."
            ),
            session_id=session_id,
        )

    client = genai.Client(api_key=settings.google_api_key)
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=message)])
    ]
    sources: list[Source] = []
    traces: list[ToolTrace] = []
    force_text = False
    append_event(session_id, {"type": "user", "text": message})

    try:
        for _ in range(6):
            config_kwargs: dict[str, Any] = {
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.4,
            }
            if force_text:
                # Tools already ran — force a written answer (no tool declarations).
                config_kwargs["tool_config"] = _tool_config("NONE")
            else:
                config_kwargs["tools"] = _gemini_tools()
                config_kwargs["tool_config"] = _tool_config("AUTO")

            response = client.models.generate_content(
                model=settings.llm_model,
                contents=contents,
                config=types.GenerateContentConfig(**config_kwargs),
            )

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content:
                break

            function_calls = [
                part.function_call
                for part in candidate.content.parts
                if getattr(part, "function_call", None)
            ]

            if not function_calls or force_text:
                reply = (response.text or "").strip()
                if not reply and traces:
                    reply = _fallback_from_tools(traces, sources)
                if not reply:
                    reply = "I have nothing to add yet."
                return _finish(reply, sources, traces, session_id, "chat_success")

            contents.append(candidate.content)
            tool_parts: list[types.Part] = []
            seen: set[str] = set()
            for call in function_calls:
                name = call.name or ""
                args: dict[str, Any] = dict(call.args or {})
                key = f"{name}:{json.dumps(args, sort_keys=True, default=str)}"
                if key in seen:
                    continue
                seen.add(key)

                result = await run_tool(name, args)
                for raw in result.get("sources") or []:
                    source = Source.model_validate(raw)
                    if not any(existing.url == source.url for existing in sources):
                        sources.append(source)
                traces.append(
                    ToolTrace(
                        name=name,
                        args=args,
                        result_preview=_preview(str(result.get("summary", ""))),
                        ok=bool(result.get("ok", False)),
                    )
                )
                append_event(
                    session_id,
                    {"type": "tool", "name": name, "args": args, "ok": result.get("ok")},
                )
                # Shrink payload: dossier keeps full sources; model only gets summary.
                tool_parts.append(
                    types.Part.from_function_response(
                        name=name,
                        response={
                            "ok": result.get("ok"),
                            "summary": result.get("summary"),
                        },
                    )
                )
            if not tool_parts:
                break
            contents.append(types.Content(role="user", parts=tool_parts))
            force_text = True

    except genai_errors.ClientError as exc:
        return ChatResponse(
            reply=(
                f"Gemini API error while using model '{settings.llm_model}': {exc}. "
                "Set LLM_MODEL in .env to a model your key can access "
                "(e.g. gemini-flash-latest)."
            ),
            session_id=session_id,
        )
    except Exception as exc:
        return ChatResponse(
            reply=f"Something went wrong talking to the model: {exc}",
            session_id=session_id,
        )

    if traces or sources:
        reply = _fallback_from_tools(traces, sources)
        return _finish(reply, sources, traces, session_id, "fallback")

    reply = "I hit a tool loop limit. Try a narrower question."
    return _finish(reply, sources, traces, session_id, "loop_limit")
