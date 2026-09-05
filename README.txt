LIVE NEWS PROXY FIX

The previous implementation called GDELT directly from the browser. Your
screenshot shows that request is ending in OFFLINE, so the news list never
loads.

This version uses the safer path:

Browser → your FastAPI /api/news → GDELT DOC 2.0

It also:
- searches the last 24 hours rather than only 6 hours
- tries a lane-specific query first
- falls back to a broad freight/market query
- returns the original article URL
- marks live=true only when GDELT actually returned articles
- keeps your old news_feed.json as an explicitly marked fallback

DO NOT replace main.jsx.

Recommended:
1. Copy backend/services/live_news_service.py into backend/services/
2. Copy apply_live_news_patch.py into the project root
3. From the project root run:
       python apply_live_news_patch.py
4. Restart:
       cd backend
       source venv/bin/activate
       python -m uvicorn main:app --reload --port 8000

Your existing CommandCenter already requests /api/news, so no frontend entry
point change is needed.

No GitHub push was performed.
