from __future__ import annotations

import asyncio
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from folio.config import get_settings
from folio.schemas import Source

WORLD_FEEDS = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.cnbc.com/id/100727362/device/rss/rss.html",
]

FINANCE_FEEDS = [
    "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    "https://feeds.marketwatch.com/marketwatch/topstories/",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
]


def _strip_html(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


async def _fetch_feed(client: httpx.AsyncClient, url: str) -> list[Source]:
    try:
        response = await client.get(url, headers={"User-Agent": "Folio/0.1"}, timeout=8.0)
        if response.status_code != 200:
            return []
        root = ET.fromstring(response.content)
        host = url.split("/")[2].replace("www.", "").split(".")[0].upper()
        items: list[Source] = []
        for item in root.findall(".//item")[:5]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            summary = _strip_html(item.findtext("description"))
            if title and link:
                items.append(
                    Source(title=f"[{host}] {title}", url=link, snippet=summary[:220])
                )
        return items
    except Exception:
        return []


async def get_world_news() -> dict[str, Any]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        batches = await asyncio.gather(*[_fetch_feed(client, u) for u in WORLD_FEEDS])
    sources = [s for batch in batches for s in batch][:12]
    if not sources:
        return {
            "ok": False,
            "summary": "World news feeds are unresponsive right now.",
            "sources": [],
        }
    lines = [f"- {s.title}" for s in sources[:8]]
    return {
        "ok": True,
        "summary": "Latest world headlines:\n" + "\n".join(lines),
        "sources": [s.model_dump() for s in sources],
    }


async def get_finance_news() -> dict[str, Any]:
    async with httpx.AsyncClient(follow_redirects=True) as client:
        batches = await asyncio.gather(*[_fetch_feed(client, u) for u in FINANCE_FEEDS])
    sources = [s for batch in batches for s in batch][:12]
    if not sources:
        return {
            "ok": False,
            "summary": "Finance feeds are unresponsive right now.",
            "sources": [],
        }
    lines = [f"- {s.title}" for s in sources[:8]]
    return {
        "ok": True,
        "summary": "Latest finance headlines:\n" + "\n".join(lines),
        "sources": [s.model_dump() for s in sources],
    }


def _search_duckduckgo(query: str, max_results: int = 6) -> list[Source]:
    with DDGS() as ddgs:
        rows = list(ddgs.text(query, max_results=max_results))
    sources: list[Source] = []
    for row in rows:
        sources.append(
            Source(
                title=row.get("title") or row.get("href") or "Result",
                url=row.get("href") or row.get("link") or "",
                snippet=(row.get("body") or "")[:240],
            )
        )
    return [s for s in sources if s.url]


async def _search_tavily(query: str) -> list[Source] | None:
    settings = get_settings()
    if not settings.tavily_api_key:
        return None
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": 6,
                "include_answer": False,
            },
        )
        response.raise_for_status()
        data = response.json()
    sources: list[Source] = []
    for row in data.get("results", []):
        sources.append(
            Source(
                title=row.get("title") or "Result",
                url=row.get("url") or "",
                snippet=(row.get("content") or "")[:240],
            )
        )
    return [s for s in sources if s.url]


async def search_web(query: str) -> dict[str, Any]:
    query = query.strip()
    if not query:
        return {"ok": False, "summary": "Empty search query.", "sources": []}
    try:
        tavily = await _search_tavily(query)
        sources = tavily if tavily is not None else await asyncio.to_thread(
            _search_duckduckgo, query
        )
    except Exception as exc:
        return {
            "ok": False,
            "summary": f"Search failed: {exc}",
            "sources": [],
        }
    if not sources:
        return {"ok": False, "summary": "No search results found.", "sources": []}
    lines = [f"- {s.title}: {s.snippet}" for s in sources[:5]]
    return {
        "ok": True,
        "summary": f"Search results for '{query}':\n" + "\n".join(lines),
        "sources": [s.model_dump() for s in sources],
    }


async def fetch_url(url: str) -> dict[str, Any]:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "summary": "URL must start with http:// or https://", "sources": []}
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            response = await client.get(url, headers={"User-Agent": "Folio/0.1"})
            response.raise_for_status()
            html = response.text
    except Exception as exc:
        return {"ok": False, "summary": f"Fetch failed: {exc}", "sources": []}

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else url)
    text = " ".join(soup.get_text(" ", strip=True).split())
    excerpt = text[:8000]
    source = Source(title=title, url=url, snippet=excerpt[:240])
    return {
        "ok": True,
        "summary": f"Fetched '{title}' ({len(excerpt)} chars):\n{excerpt[:3000]}",
        "sources": [source.model_dump()],
    }


TOOL_SPECS = [
    {
        "name": "search_web",
        "description": "Search the live web for a query. Use for facts, current events, or anything needing sources.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": "Fetch and extract main text from a URL the user wants summarized or cited.",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "get_world_news",
        "description": "Fetch latest world news headlines from major RSS outlets.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "get_finance_news",
        "description": "Fetch latest finance and market headlines from major RSS outlets.",
        "parameters": {"type": "object", "properties": {}},
    },
]


async def run_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "search_web":
        return await search_web(str(args.get("query", "")))
    if name == "fetch_url":
        return await fetch_url(str(args.get("url", "")))
    if name == "get_world_news":
        return await get_world_news()
    if name == "get_finance_news":
        return await get_finance_news()
    return {"ok": False, "summary": f"Unknown tool: {name}", "sources": []}
