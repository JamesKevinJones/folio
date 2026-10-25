import pytest

from folio.config import get_settings


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Point data/ at a temp dir and blank every key, so no test touches the repo
    or calls a real API, even when a developer's .env holds real keys."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    for key in ("GOOGLE_API_KEY", "OPENAI_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.setenv(key, "")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()
