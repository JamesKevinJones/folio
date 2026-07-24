from __future__ import annotations

import io

from openai import OpenAI

from folio.config import get_settings


def transcribe_audio(data: bytes, filename: str = "audio.webm") -> str:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for transcription.")
    client = OpenAI(api_key=settings.openai_api_key)
    buffer = io.BytesIO(data)
    buffer.name = filename
    result = client.audio.transcriptions.create(
        model=settings.stt_model,
        file=buffer,
    )
    return (result.text or "").strip()


def synthesize_speech(text: str) -> bytes:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for speech synthesis.")
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.audio.speech.create(
        model=settings.tts_model,
        voice=settings.tts_voice,
        input=text[:4000],
    )
    return response.content
