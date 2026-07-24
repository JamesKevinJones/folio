import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  chat,
  exportBrief,
  getHealth,
  getSettings,
  putSettings,
} from "./api";
import { BootSplash, BracketStatus, Counter, IdleHero } from "./components/ui/Chrome";
import { PixelIcon } from "./components/ui/PixelIcon";
import type {
  AgentStatus,
  ChatMessage,
  DossierView,
  Section,
  Source,
  ToolTrace,
} from "./types";
import { browserVoiceSupported, createHoldToTalk, speakBrowser } from "./voice/browser";
import { eventsWsUrl } from "./config";
import "./app.css";

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function padClock(d: Date) {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function App() {
  const [booting, setBooting] = useState(true);
  const [ready, setReady] = useState(false);
  const [section, setSection] = useState<Section>("chat");
  const [status, setStatus] = useState<AgentStatus>("boot");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [traces, setTraces] = useState<ToolTrace[]>([]);
  const [input, setInput] = useState("");
  const [dossierView, setDossierView] = useState<DossierView>("grid");
  const [showGrid, setShowGrid] = useState(false);
  const [clock, setClock] = useState(padClock(new Date()));
  const [recording, setRecording] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [browserVoice, setBrowserVoice] = useState({ stt: false, tts: false });
  const [health, setHealth] = useState<{
    version: string;
    llm_ready: boolean;
    voice_ready: boolean;
  } | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const pttRef = useRef(createHoldToTalk({}));

  useEffect(() => {
    const id = window.setInterval(() => setClock(padClock(new Date())), 1000);
    return () => window.clearInterval(id);
  }, []);

  useEffect(() => {
    const support = browserVoiceSupported();
    setBrowserVoice(support);
    pttRef.current = createHoldToTalk({
      onError: (message) => setError(message),
    });
    // Chrome loads voices asynchronously
    window.speechSynthesis?.getVoices();
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [h, s] = await Promise.all([getHealth(), getSettings()]);
        if (cancelled) return;
        setHealth(h);
        setShowGrid(s.show_grid);
        setDossierView(s.dossier_view);
        setReady(true);
        setStatus("idle");
        window.setTimeout(() => setBooting(false), 500);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to reach Folio sidecar");
        setStatus("error");
        setReady(true);
        window.setTimeout(() => setBooting(false), 700);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const ws = new WebSocket(eventsWsUrl());
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "status" && data.value) {
          setStatus(data.value as AgentStatus);
        }
        if (data.type === "tool") {
          setTraces((prev) => [
            ...prev,
            {
              name: data.name,
              args: data.args || {},
              result_preview: data.preview || "",
              ok: Boolean(data.ok),
            },
          ]);
          setStatus("tool_running");
        }
        if (data.type === "sources" && Array.isArray(data.sources)) {
          setSources(data.sources);
        }
      } catch {
        /* ignore */
      }
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const msgCount = messages.length;
  const srcCount = sources.length;
  const lastExchange = useMemo(() => {
    const user = [...messages].reverse().find((m) => m.role === "user");
    const assistant = [...messages].reverse().find((m) => m.role === "assistant");
    return { question: user?.text || "", answer: assistant?.text || "" };
  }, [messages]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    setError(null);
    setInput("");
    setTraces([]);
    const userMsg: ChatMessage = { id: uid(), role: "user", text: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setStatus("thinking");
    try {
      const result = await chat(trimmed);
      setSources(result.sources);
      setTraces(result.tool_traces);
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: "assistant",
          text: result.reply,
          sources: result.sources,
          tool_traces: result.tool_traces,
        },
      ]);
      if (browserVoice.tts) {
        try {
          setStatus("speaking");
          await speakBrowser(result.reply);
        } catch {
          /* voice optional */
        }
      }
      setStatus("idle");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Chat failed");
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void sendMessage(input);
  }

  async function toggleDossierView(view: DossierView) {
    setDossierView(view);
    await putSettings({ dossier_view: view });
  }

  async function toggleGrid(next: boolean) {
    setShowGrid(next);
    await putSettings({ show_grid: next });
  }

  async function onExport() {
    const result = await exportBrief({
      question: lastExchange.question,
      answer: lastExchange.answer,
      sources,
    });
    const blob = new Blob([result.markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "folio-brief.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  function startPtt() {
    if (!pttRef.current.supported) {
      setError("Free voice needs Chrome or Edge (Web Speech API).");
      return;
    }
    setError(null);
    setRecording(true);
    setStatus("listening");
    pttRef.current.start();
  }

  async function stopPtt() {
    if (!recording) return;
    setRecording(false);
    const text = await pttRef.current.stop();
    if (text) await sendMessage(text);
    else setStatus("idle");
  }

  const statusLabel =
    status === "tool_running"
      ? "sources"
      : status === "boot"
        ? "loading"
        : status;

  return (
    <>
      {booting && <BootSplash ready={ready} />}
      {showGrid && <div className="grid-overlay" aria-hidden />}
      <div className="shell">
        <aside className="rail">
          <div className="rail-mark">F</div>
          {(
            [
              ["chat", "Chat"],
              ["dossier", "Dossier"],
              ["settings", "Settings"],
              ["about", "About"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              className={section === id ? "active" : ""}
              onClick={() => setSection(id)}
              type="button"
            >
              {label}
            </button>
          ))}
        </aside>

        <div className="main">
          <header className="top">
            <div className="brand">
              <strong>FOLIO</strong>
              <span className="sep">/</span>
              <span>{section}</span>
            </div>
            <div className="meta">
              <Counter label="MSG" value={msgCount} />
              <Counter label="SRC" value={srcCount} />
              <BracketStatus value={statusLabel} />
              <span className="clock">{clock}</span>
            </div>
          </header>

          <div className="panes">
            <section className={`pane chat-pane ${section === "chat" ? "focus" : ""}`}>
              {messages.length === 0 ? (
                <IdleHero />
              ) : (
                <div className="transcript" ref={listRef}>
                  {messages.map((m) => (
                    <article key={m.id} className={`bubble ${m.role}`}>
                      <div className="bubble-role">{m.role === "user" ? "you" : "folio"}</div>
                      <p>{m.text}</p>
                    </article>
                  ))}
                </div>
              )}

              {traces.length > 0 && (
                <div className="marquee" aria-live="polite">
                  <div className="marquee-track">
                    {traces.map((t, i) => (
                      <span key={`${t.name}-${i}`}>
                        <PixelIcon name={t.name.includes("news") ? "news" : t.name.includes("fetch") ? "link" : "search"} active />
                        {t.name}
                        {t.result_preview ? ` — ${t.result_preview.slice(0, 80)}` : ""}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <form className="askbar" onSubmit={onSubmit}>
                <button
                  type="button"
                  className={`ptt ${recording ? "recording" : ""}`}
                  onMouseDown={() => void startPtt()}
                  onMouseUp={stopPtt}
                  onMouseLeave={() => recording && stopPtt()}
                  onTouchStart={(e) => {
                    e.preventDefault();
                    void startPtt();
                  }}
                  onTouchEnd={stopPtt}
                  title="Hold to talk"
                >
                  <PixelIcon name="mic" active={recording} size={18} />
                </button>
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask Folio…"
                  aria-label="Ask Folio"
                />
                <button className="primary" type="submit">
                  Ask Folio
                </button>
              </form>
              {error && <div className="error-line">[error] {error}</div>}
            </section>

            <section className={`pane dossier-pane ${section === "dossier" ? "focus" : ""}`}>
              <div className="dossier-head">
                <h2>Source Dossier</h2>
                <div className="view-toggle">
                  <button
                    type="button"
                    className={dossierView === "grid" ? "active" : ""}
                    onClick={() => void toggleDossierView("grid")}
                  >
                    <PixelIcon name="grid" active={dossierView === "grid"} /> Grid
                  </button>
                  <button
                    type="button"
                    className={dossierView === "marquee" ? "active" : ""}
                    onClick={() => void toggleDossierView("marquee")}
                  >
                    <PixelIcon name="marquee" active={dossierView === "marquee"} /> Marquee
                  </button>
                  <button type="button" onClick={() => void onExport()}>
                    <PixelIcon name="export" /> [export]
                  </button>
                </div>
              </div>

              {sources.length === 0 ? (
                <p className="empty">
                  Waiting for research. Ask something in Chat (news, a question, or a URL) — live
                  sources will show up here.
                </p>
              ) : dossierView === "marquee" ? (
                <div className="marquee dossier-marquee">
                  <div className="marquee-track">
                    {sources.map((s, i) => (
                      <a key={`${s.url}-${i}`} href={s.url} target="_blank" rel="noreferrer">
                        {String(i + 1).padStart(2, "0")} {s.title}
                      </a>
                    ))}
                  </div>
                </div>
              ) : (
                <ol className="source-grid">
                  {sources.map((s, i) => (
                    <li key={`${s.url}-${i}`}>
                      <div className="idx">{String(i + 1).padStart(2, "0")}</div>
                      <div>
                        <a href={s.url} target="_blank" rel="noreferrer">
                          {s.title}
                        </a>
                        <p>{s.snippet}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>

          {section === "settings" && (
            <div className="overlay-panel">
              <h2>Settings</h2>
              <label className="check">
                <input
                  type="checkbox"
                  checked={showGrid}
                  onChange={(e) => void toggleGrid(e.target.checked)}
                />
                Show grid overlay
              </label>
              <p className="hint">
                Secrets live in <code>.env</code> (<code>GOOGLE_API_KEY</code> for chat). Voice is
                free via the browser (Chrome/Edge Web Speech) — no OpenAI key needed.
              </p>
              <ul className="key-status">
                <li>LLM ready: {health?.llm_ready ? "yes" : "no"}</li>
                <li>
                  Free voice STT: {browserVoice.stt ? "yes" : "no (use Chrome/Edge)"}
                </li>
                <li>Free voice TTS: {browserVoice.tts ? "yes" : "no"}</li>
              </ul>
            </div>
          )}

          {section === "about" && (
            <div className="overlay-panel">
              <h2>About Folio</h2>
              <p>Personal research desk. Ask anything. See the sources.</p>
              <p>Version {health?.version || "0.1.0"} · MIT</p>
              <p>Not a Jarvis/Friday clone — evidence-first companion.</p>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
