export type Source = {
  title: string;
  url: string;
  snippet?: string;
  index?: number | null;
};

export type ToolTrace = {
  name: string;
  args: Record<string, unknown>;
  result_preview: string;
  ok: boolean;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  sources?: Source[];
  tool_traces?: ToolTrace[];
};

export type AgentStatus =
  | "boot"
  | "idle"
  | "listening"
  | "thinking"
  | "tool_running"
  | "speaking"
  | "error";

export type Section = "chat" | "dossier" | "settings" | "about";
export type DossierView = "grid" | "marquee";
