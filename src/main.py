import asyncio
import hashlib
import os
import re
import time
from typing import Optional
from urllib.parse import quote_plus, urlparse

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Searchr")
app.mount("/static", StaticFiles(directory="/app/static"), name="static")

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def dedupe(results: list[dict]) -> list[dict]:
    seen_urls = set()
    seen_titles = set()
    out = []
    for r in results:
        url_key = re.sub(r"https?://", "", r.get("url", "")).rstrip("/")
        title_key = r.get("title", "").lower().strip()[:60]
        if url_key not in seen_urls and title_key not in seen_titles:
            seen_urls.add(url_key)
            seen_titles.add(title_key)
            out.append(r)
    return out


async def search_google(query: str, client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        url = f"https://www.google.com/search?q={quote_plus(query)}&num=10&hl=en"
        resp = await client.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        for g in soup.select("div.g"):
            title_el = g.select_one("h3")
            link_el = g.select_one("a[href]")
            snippet_el = g.select_one("div.VwiC3b, span.aCOpRe, div[data-sncf]")
            if not title_el or not link_el:
                continue
            href = link_el["href"]
            if href.startswith("/url?q="):
                href = href.split("/url?q=")[1].split("&")[0]
            if not href.startswith("http"):
                continue
            results.append({
                "title": title_el.get_text(),
                "url": href,
                "snippet": snippet_el.get_text() if snippet_el else "",
                "source": "google",
            })
    except Exception as e:
        print(f"Google error: {e}")
    return results


async def search_brave(query: str, client: httpx.AsyncClient) -> list[dict]:
    if not BRAVE_API_KEY:
        return []
    results = []
    try:
        resp = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 10},
            headers={"Accept": "application/json", "X-Subscription-Token": BRAVE_API_KEY},
            timeout=8,
        )
        data = resp.json()
        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("description", ""),
                "source": "brave",
            })
    except Exception as e:
        print(f"Brave error: {e}")
    return results


async def search_duckduckgo(query: str, client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        # Step 1: get vqd token
        resp = await client.get(
            "https://duckduckgo.com/",
            params={"q": query},
            headers=HEADERS,
            timeout=8,
        )
        vqd_match = re.search(r'vqd=(["\'])([^"\']+)\1', resp.text)
        if not vqd_match:
            vqd_match = re.search(r'vqd=([\d-]+)', resp.text)
            vqd = vqd_match.group(1) if vqd_match else None
        else:
            vqd = vqd_match.group(2)

        if not vqd:
            return []

        # Step 2: hit the HTML results endpoint
        resp2 = await client.get(
            "https://duckduckgo.com/html/",
            params={"q": query, "vqd": vqd},
            headers={**HEADERS, "Referer": "https://duckduckgo.com/"},
            timeout=8,
        )
        soup = BeautifulSoup(resp2.text, "html.parser")
        for result in soup.select(".result__body"):
            title_el = result.select_one(".result__title a")
            snippet_el = result.select_one(".result__snippet")
            if not title_el:
                continue
            href = title_el.get("href", "")
            # DDG wraps URLs; unwrap if needed
            if "uddg=" in href:
                from urllib.parse import unquote
                href = unquote(href.split("uddg=")[-1].split("&")[0])
            if not href.startswith("http"):
                continue
            results.append({
                "title": title_el.get_text(strip=True),
                "url": href,
                "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                "source": "duckduckgo",
            })
    except Exception as e:
        print(f"DuckDuckGo error: {e}")
    return results


async def search_wikipedia(query: str, client: httpx.AsyncClient) -> list[dict]:
    results = []
    try:
        resp = await client.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": 5,
                "srprop": "snippet",
            },
            timeout=8,
        )
        data = resp.json()
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            snippet = BeautifulSoup(item.get("snippet", ""), "html.parser").get_text()
            results.append({
                "title": title,
                "url": f"https://en.wikipedia.org/wiki/{quote_plus(title.replace(' ', '_'))}",
                "snippet": snippet + "...",
                "source": "wikipedia",
            })
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return results


def merge_results(google: list, brave: list, ddg: list, wiki: list) -> list[dict]:
    """Merge results: boost URLs appearing in multiple sources, wiki ranked lower."""
    url_map: dict[str, dict] = {}
    for result in google + brave + ddg + wiki:
        key = re.sub(r"https?://", "", result["url"]).rstrip("/")
        if key not in url_map:
            url_map[key] = {**result, "score": 0, "sources": []}
        url_map[key]["score"] += 2 if result["source"] in ("google", "brave", "duckduckgo") else 1
        if result["source"] not in url_map[key]["sources"]:
            url_map[key]["sources"].append(result["source"])

    merged = sorted(url_map.values(), key=lambda x: -x["score"])
    return dedupe(merged)


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("/app/static/index.html") as f:
        return f.read()


@app.get("/search")
async def search(q: str = Query(..., min_length=1)):
    start = time.time()
    async with httpx.AsyncClient(follow_redirects=True) as client:
        google, brave, ddg, wiki = await asyncio.gather(
            search_google(q, client),
            search_brave(q, client),
            search_duckduckgo(q, client),
            search_wikipedia(q, client),
        )

    results = merge_results(google, brave, ddg, wiki)
    elapsed = round((time.time() - start) * 1000)
    return JSONResponse({
        "query": q,
        "results": results,
        "count": len(results),
        "elapsed_ms": elapsed,
        "sources": {
            "google": len(google),
            "brave": len(brave),
            "duckduckgo": len(ddg),
            "wikipedia": len(wiki),
        },
    })
