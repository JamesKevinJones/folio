/** Empty = same origin (local sidecar / Vite proxy). Set VITE_API_BASE on Vercel. */
export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") || "";

export function apiUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
}

export function eventsWsUrl(): string {
  if (API_BASE) {
    const base = new URL(API_BASE);
    const proto = base.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${base.host}/api/events`;
  }
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/api/events`;
}
