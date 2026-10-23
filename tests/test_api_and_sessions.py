import httpx
from fastapi.testclient import TestClient

from folio.api.app import app
from folio.memory import session
from folio.tools import research


def test_session_ids_cannot_leave_the_sessions_folder(isolated_settings):
    session.append_event("../../escape", {"type": "user", "text": "hi"})
    sessions = isolated_settings.data_dir / "sessions"
    assert [p.name for p in sessions.iterdir()] == ["escape.jsonl"]
    assert session.load_events("../../escape")[0]["text"] == "hi"


def test_brief_export_cannot_write_outside_the_briefs_folder(isolated_settings):
    _, path = session.export_brief_markdown("q", "a", [], session_id="../../escape")
    briefs = (isolated_settings.data_dir / "briefs").resolve()
    assert path.resolve().parent == briefs


def test_brief_export_numbers_its_sources():
    with TestClient(app) as client:
        response = client.post(
            "/api/briefs/export",
            json={
                "question": "Q?",
                "answer": "A.",
                "sources": [
                    {"title": "First", "url": "https://one.test", "snippet": "s1"},
                    {"title": "Second", "url": "https://two.test"},
                ],
            },
        )
    assert response.status_code == 200
    markdown = response.json()["markdown"]
    assert "1. **First**" in markdown and "https://one.test" in markdown
    assert "2. **Second**" in markdown


def test_health_reports_the_model_unavailable_without_a_key():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["llm_ready"] is False


async def test_fetch_url_keeps_the_text_and_drops_scripts_and_chrome(monkeypatch):
    page = (
        "<html><head><title>Paper</title><script>track()</script></head>"
        "<body><nav>Menu</nav><p>The finding is 42.</p><footer>(c)</footer></body></html>"
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=page))
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        research.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
    )

    result = await research.fetch_url("https://paper.test/x")

    assert result["ok"] is True
    assert result["sources"][0]["title"] == "Paper"
    assert "The finding is 42." in result["summary"]
    assert "track()" not in result["summary"] and "Menu" not in result["summary"]


async def test_search_uses_duckduckgo_when_no_tavily_key_is_set(monkeypatch):
    seen = []

    def fake_ddg(query, max_results=6):
        seen.append(query)
        return [research.Source(title="Hit", url="https://hit.test", snippet="body")]

    monkeypatch.setattr(research, "_search_duckduckgo", fake_ddg)

    result = await research.search_web("rust release")

    assert seen == ["rust release"]
    assert result["ok"] is True and "Hit" in result["summary"]


async def test_an_unknown_tool_is_refused_not_raised():
    result = await research.run_tool("delete_everything", {})
    assert result["ok"] is False
