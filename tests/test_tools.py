import xml.etree.ElementTree as ET

import pytest

from folio.schemas import Source
from folio.tools.research import _strip_html, fetch_url, get_world_news, search_web


def test_strip_html():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_source_model():
    source = Source(title="Example", url="https://example.com", snippet="hi")
    assert source.url.startswith("https://")


@pytest.mark.asyncio
async def test_fetch_url_rejects_bad_scheme():
    result = await fetch_url("ftp://example.com")
    assert result["ok"] is False
    assert result["sources"] == []


@pytest.mark.asyncio
async def test_search_web_empty_query():
    result = await search_web("   ")
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_get_world_news_shape(monkeypatch):
    async def fake_feed(client, url):
        return [
            Source(title="[BBC] Sample", url="https://example.com/a", snippet="snippet")
        ]

    monkeypatch.setattr("folio.tools.research._fetch_feed", fake_feed)
    result = await get_world_news()
    assert result["ok"] is True
    assert len(result["sources"]) >= 1
    assert "Sample" in result["summary"]


def test_rss_parse_smoke():
    xml = """<?xml version='1.0'?><rss><channel>
    <item><title>T</title><link>https://x.test</link><description>D</description></item>
    </channel></rss>"""
    root = ET.fromstring(xml)
    assert root.find(".//item/title").text == "T"
