# Searchr

Lightweight personal search aggregator. Queries DuckDuckGo, Brave Search, and Wikipedia in parallel and merges results.

## Setup

### 1. Get a Brave Search API key (optional)
Go to https://brave.com/search/api/ — free tier is 2,000 queries/month but requires a credit card. Skip if unavailable; DuckDuckGo + Wikipedia still work great.

### 2. Create a `.env` file
```
BRAVE_API_KEY=your_key_here
```
Leave it empty to skip Brave. DuckDuckGo and Wikipedia need no key.

### 3. Run with Docker Compose
```bash
docker compose up -d --build
```

Open http://localhost:6969

### Run natively (without Docker)
```bash
pip install -r requirements.txt
BRAVE_API_KEY=your_key uvicorn src.main:app --host 0.0.0.0 --port 6969 --reload
```

## Browser default search engine

Add this URL as a custom search engine in your browser:

```
http://your-server-ip:6969/search?q=%s
```

- **Firefox**: Settings → Search → Add search engine
- **Chrome/Brave**: Settings → Search engine → Manage → Add

## API

| Endpoint | Description |
|---|---|
| `GET /` | Home page |
| `GET /search?q=query` | Search page (browser-friendly) |
| `GET /api/search?q=query` | JSON results |
| `GET /api/debug?q=query` | Raw per-source results for debugging |

## Updating

```bash
git pull
docker compose down && docker compose up -d --build
```

## Notes

- Google scraping is omitted — VPS IPs get blocked. DuckDuckGo is more reliable.
- Results appearing in multiple sources are ranked higher automatically.
- `.env` is gitignored — create it manually on each device.
