import type { Source, ToolTrace } from "./types";
import { apiUrl } from "./config";

const json = async <T>(res: Response): Promise<T> => {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
};

export async function getHealth() {
  return json<{
    status: string;
    version: string;
    llm_ready: boolean;
    voice_ready: boolean;
  }>(await fetch(apiUrl("/api/health")));
}

export async function getSettings() {
  return json<{
    llm_model: string;
    stt_model: string;
    tts_model: string;
    tts_voice: string;
    has_google_key: boolean;
    has_openai_key: boolean;
    has_tavily_key: boolean;
    show_grid: boolean;
    dossier_view: "grid" | "marquee";
  }>(await fetch(apiUrl("/api/settings")));
}

export async function putSettings(payload: {
  show_grid?: boolean;
  dossier_view?: "grid" | "marquee";
}) {
  return json(
    await fetch(apiUrl("/api/settings"), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}

export async function chat(message: string, sessionId = "default") {
  return json<{
    reply: string;
    sources: Source[];
    tool_traces: ToolTrace[];
    session_id: string;
  }>(
    await fetch(apiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
  );
}

export async function transcribe(blob: Blob) {
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  return json<{ text: string }>(
    await fetch(apiUrl("/api/voice/transcribe"), { method: "POST", body: form }),
  );
}

export async function speak(text: string) {
  const res = await fetch(apiUrl("/api/voice/speak"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.blob();
}

export async function exportBrief(payload: {
  question: string;
  answer: string;
  sources: Source[];
  session_id?: string;
}) {
  return json<{ markdown: string; path: string }>(
    await fetch(apiUrl("/api/briefs/export"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
}
