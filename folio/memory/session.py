from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from folio.config import get_settings


def _safe_id(session_id: str) -> str:
    """session_id arrives from the HTTP request, so it must never shape a path."""
    return "".join(c for c in session_id if c.isalnum() or c in ("-", "_")) or "default"


def _session_path(session_id: str) -> Path:
    return get_settings().data_dir / "sessions" / f"{_safe_id(session_id)}.jsonl"


def append_event(session_id: str, event: dict[str, Any]) -> None:
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        **event,
    }
    path = _session_path(session_id)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_events(session_id: str, limit: int = 40) -> list[dict[str, Any]]:
    path = _session_path(session_id)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def export_brief_markdown(
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    session_id: str = "default",
) -> tuple[str, Path]:
    lines = [
        "# Folio brief",
        "",
        f"_Exported {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Question",
        question or "(none)",
        "",
        "## Answer",
        answer or "(none)",
        "",
        "## Sources",
    ]
    if not sources:
        lines.append("_No sources attached._")
    else:
        for i, source in enumerate(sources, start=1):
            title = source.get("title") or "Source"
            url = source.get("url") or ""
            snippet = source.get("snippet") or ""
            lines.append(f"{i}. **{title}**")
            if url:
                lines.append(f"   - {url}")
            if snippet:
                lines.append(f"   - {snippet}")
    markdown = "\n".join(lines) + "\n"
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = get_settings().data_dir / "briefs" / f"{_safe_id(session_id)}-{stamp}.md"
    path.write_text(markdown, encoding="utf-8")
    return markdown, path
