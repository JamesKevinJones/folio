from __future__ import annotations

import asyncio
import json

from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from folio import __version__
from folio.agent import run_chat
from folio.api.events import hub
from folio.config import get_settings
from folio.memory import export_brief_markdown
from folio.schemas import (
    BriefExportRequest,
    BriefExportResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    SettingsPublic,
)
from folio.voice import synthesize_speech, transcribe_audio

app = FastAPI(title="Folio", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_prefs_path = get_settings().data_dir / "prefs.json"


def _load_prefs() -> dict:
    if _prefs_path.exists():
        return json.loads(_prefs_path.read_text(encoding="utf-8"))
    return {"show_grid": False, "dossier_view": "grid"}


def _save_prefs(prefs: dict) -> None:
    _prefs_path.write_text(json.dumps(prefs, indent=2), encoding="utf-8")


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=__version__,
        llm_ready=bool(settings.google_api_key),
        # Browser Web Speech is free and default; OpenAI voice is optional legacy.
        voice_ready=True,
    )


@app.get("/api/settings", response_model=SettingsPublic)
async def get_public_settings() -> SettingsPublic:
    settings = get_settings()
    prefs = _load_prefs()
    return SettingsPublic(
        llm_model=settings.llm_model,
        stt_model=settings.stt_model,
        tts_model=settings.tts_model,
        tts_voice=settings.tts_voice,
        has_google_key=bool(settings.google_api_key),
        has_openai_key=bool(settings.openai_api_key),
        has_tavily_key=bool(settings.tavily_api_key),
        show_grid=bool(prefs.get("show_grid", False)),
        dossier_view=str(prefs.get("dossier_view", "grid")),
    )


@app.put("/api/settings", response_model=SettingsPublic)
async def put_settings(payload: dict) -> SettingsPublic:
    prefs = _load_prefs()
    if "show_grid" in payload:
        prefs["show_grid"] = bool(payload["show_grid"])
    if "dossier_view" in payload and payload["dossier_view"] in ("grid", "marquee"):
        prefs["dossier_view"] = payload["dossier_view"]
    _save_prefs(prefs)
    return await get_public_settings()


@app.post("/api/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    await hub.publish({"type": "status", "value": "thinking"})
    result = await run_chat(body.message, body.session_id)
    for trace in result.tool_traces:
        await hub.publish(
            {
                "type": "tool",
                "name": trace.name,
                "args": trace.args,
                "preview": trace.result_preview,
                "ok": trace.ok,
            }
        )
    await hub.publish(
        {
            "type": "sources",
            "sources": [s.model_dump() for s in result.sources],
        }
    )
    await hub.publish({"type": "status", "value": "idle"})
    return result


@app.post("/api/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...)) -> dict:
    await hub.publish({"type": "status", "value": "listening"})
    data = await file.read()
    text = await asyncio.to_thread(transcribe_audio, data, file.filename or "audio.webm")
    await hub.publish({"type": "transcript", "role": "user", "text": text})
    await hub.publish({"type": "status", "value": "idle"})
    return {"text": text}


@app.post("/api/voice/speak")
async def voice_speak(payload: dict) -> Response:
    text = str(payload.get("text", "")).strip()
    if not text:
        return Response(status_code=400, content=b"empty text")
    await hub.publish({"type": "status", "value": "speaking"})
    audio = await asyncio.to_thread(synthesize_speech, text)
    await hub.publish({"type": "status", "value": "idle"})
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/briefs/export", response_model=BriefExportResponse)
async def export_brief(body: BriefExportRequest) -> BriefExportResponse:
    markdown, path = export_brief_markdown(
        question=body.question,
        answer=body.answer,
        sources=[s.model_dump() for s in body.sources],
        session_id=body.session_id,
    )
    return BriefExportResponse(markdown=markdown, path=str(path))


@app.websocket("/api/events")
async def events_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = hub.subscribe()
    try:
        await websocket.send_json({"type": "status", "value": "idle"})
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        hub.unsubscribe(queue)
    except Exception:
        hub.unsubscribe(queue)


def mount_companion(application: FastAPI) -> None:
    dist = get_settings().companion_dist
    if not dist.exists():
        return
    assets = dist / "assets"
    if assets.exists():
        application.mount("/assets", StaticFiles(directory=assets), name="assets")

    @application.get("/")
    async def index() -> FileResponse:
        return FileResponse(dist / "index.html")

    @application.get("/{full_path:path}")
    async def spa(full_path: str) -> FileResponse:
        candidate = dist / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")
