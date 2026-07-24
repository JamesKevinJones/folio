from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Source(BaseModel):
    title: str
    url: str
    snippet: str = ""
    index: int | None = None


class ToolTrace(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result_preview: str = ""
    ok: bool = True


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    sources: list[Source] = Field(default_factory=list)
    tool_traces: list[ToolTrace] = Field(default_factory=list)
    session_id: str = "default"


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_ready: bool
    voice_ready: bool


class BriefExportRequest(BaseModel):
    session_id: str = "default"
    question: str = ""
    answer: str = ""
    sources: list[Source] = Field(default_factory=list)


class BriefExportResponse(BaseModel):
    markdown: str
    path: str


class SettingsPublic(BaseModel):
    llm_model: str
    stt_model: str
    tts_model: str
    tts_voice: str
    has_google_key: bool
    has_openai_key: bool
    has_tavily_key: bool
    show_grid: bool = False
    dossier_view: str = "grid"
