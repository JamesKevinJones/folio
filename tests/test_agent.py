from types import SimpleNamespace

from google.genai import errors as genai_errors

from folio.agent import loop


def _call(name, **args):
    return SimpleNamespace(function_call=SimpleNamespace(name=name, args=args))


def _response(*parts, text=""):
    content = SimpleNamespace(parts=list(parts))
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)], text=text)


class FakeClient:
    """Stands in for genai.Client: replays scripted responses, records configs."""

    def __init__(self, responses):
        self.configs = []
        responses = list(responses)

        def generate_content(model, contents, config):
            self.configs.append(config)
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        self.models = SimpleNamespace(generate_content=generate_content)


def _use(monkeypatch, client, tool_results=None):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    loop.get_settings.cache_clear()
    monkeypatch.setattr(loop.genai, "Client", lambda api_key: client)
    calls = []

    async def fake_run_tool(name, args):
        calls.append((name, args))
        return tool_results or {"ok": True, "summary": "found it", "sources": []}

    monkeypatch.setattr(loop, "run_tool", fake_run_tool)
    return calls


async def test_without_a_key_it_says_so_instead_of_calling_gemini():
    response = await loop.run_chat("hello")
    assert "GOOGLE_API_KEY" in response.reply
    assert response.sources == []


async def test_tool_results_become_indexed_deduplicated_sources(monkeypatch):
    client = FakeClient(
        [
            # The model asks for the same search twice in one turn.
            _response(_call("search_web", query="rust"), _call("search_web", query="rust")),
            _response(text="Rust 2.0 shipped. [1]"),
        ]
    )
    calls = _use(
        monkeypatch,
        client,
        {
            "ok": True,
            "summary": "results",
            "sources": [
                {"title": "A", "url": "https://a.test"},
                {"title": "A again", "url": "https://a.test"},
                {"title": "B", "url": "https://b.test"},
            ],
        },
    )

    response = await loop.run_chat("what's new in rust?")

    assert response.reply == "Rust 2.0 shipped. [1]"
    assert calls == [("search_web", {"query": "rust"})]
    assert [(s.index, s.url) for s in response.sources] == [
        (1, "https://a.test"),
        (2, "https://b.test"),
    ]
    assert [t.name for t in response.tool_traces] == ["search_web"]
    # After tools ran, the next turn must be forced to answer in text.
    assert client.configs[1].tool_config.function_calling_config.mode == "NONE"


async def test_an_empty_answer_after_tools_falls_back_to_the_tool_summary(monkeypatch):
    client = FakeClient([_response(_call("get_world_news")), _response(text="")])
    _use(
        monkeypatch,
        client,
        {"ok": True, "summary": "Headline one", "sources": [{"title": "T", "url": "https://t.test"}]},
    )

    response = await loop.run_chat("news?")

    assert response.reply.startswith("Headline one")
    assert "dossier" in response.reply


async def test_a_gemini_client_error_names_the_model_to_change(monkeypatch):
    client = FakeClient([genai_errors.ClientError(404, {"error": {"message": "no such model"}})])
    _use(monkeypatch, client)

    response = await loop.run_chat("hi")

    assert "gemini-flash-latest" in response.reply
    assert "LLM_MODEL" in response.reply
