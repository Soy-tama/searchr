# Searchr

Lightweight personal search aggregator. Queries Google, Brave Search, and Wikipedia in parallel and merges results.

## Setup

### 1. Get a Brave Search API key (free)
1. Go to https://brave.com/search/api/
2. Sign up for the free tier (2,000 queries/month)
3. Copy your API key

### 2. Create a `.env` file
```
BRAVE_API_KEY=your_key_here
```
Wikipedia works without a key. Google is scraped (no key needed, but may occasionally be blocked by bot detection).

### 3. Run with Docker Compose
```bash
docker compose up -d --build
```

Open http://localhost:4444

### Run natively (without Docker)
```bash
pip install -r requirements.txt
BRAVE_API_KEY=your_key uvicorn src.main:app --host 0.0.0.0 --port 4444 --reload
```

## Notes
- Google scraping works without a key but can be rate-limited. If you want reliability, consider the SerpAPI or ScaleSerp free tiers instead.
- Results are merged and deduplicated. URLs appearing in both Google and Brave are ranked higher.
- Filter by source using the pills on the results page.
