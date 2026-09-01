# FreightOne — SIH 2026 (Problem Statement 26006)

**Intelligent Freight Forecasting Model for Optimized Vessel Chartering and Bulk Cargo Procurement from overseas to East Coast of India**

## Architecture

```
FreightOne/
├── backend/
│   ├── main.py                 # FastAPI entry + all routes
│   ├── requirements.txt
│   ├── data/                   # ← EDIT THESE to update real data later
│   │   ├── managers.json
│   │   ├── materials.json
│   │   ├── source_ports.json
│   │   ├── destination_ports.json
│   │   ├── cargo_prices.json
│   │   ├── inland_transport.json
│   │   ├── consignments.json
│   │   ├── plants.json
│   │   ├── bdi_history.json
│   │   └── news_feed.json
│   └── services/
│       ├── data_loader.py      # Single place that reads JSON
│       ├── bdi_forecast.py     # Holt + seasonal 90-day forecast
│       ├── risk_analyzer.py    # Weather + market + congestion score
│       ├── route_optimizer.py  # Cost / time / risk ranking engine
│       └── geo.py              # Haversine distance helpers
└── frontend/
    └── src/
        ├── main.jsx / App.jsx
        ├── api.js
        ├── styles.css          # Original visual design (unchanged)
        ├── components/         # Login, Shell, KPI, Chart, Field…
        └── pages/              # One file per left-nav module
```

## Demo logins (Manager Profiling)

| User ID   | Password | Plant                          |
|-----------|----------|--------------------------------|
| r.sharma  | sail123  | Rourkela Steel Plant (RSP)     |
| a.patel   | sail456  | Bhilai Steel Plant (BSP)       |
| s.nair    | sail789  | Visakhapatnam Steel Plant (VSP)|
| k.reddy   | sail321  | IISCO Steel Plant (ISP)        |

## Run

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173

## What is now dynamic

1. **Command Center** — live BDI series, network risk, AI procurement signal from inventory urgency, live news, consignments from DB.
2. **Procurement Planner** — real landed-cost calculation (FOB + freight from distance/BDI + inland rail) + urgency from stock & incoming.
3. **Freight Intelligence** — 180-day history + 90-day Holt-seasonal forecast, booking window at lowest projected BDI, weather series.
4. **Port Optimiser** — ranks all capable East Coast ports with explainable weights (cost / time / risk / historic preference).
5. **Consignment Tracker** — full list from `consignments.json` (delivered / active / delayed / future).
6. **What-if** — side-by-side preferred vs best alternative with real cost & ETA deltas.
7. **Alert Center** — generated from delayed vessels, weather level, BDI trend, inventory urgency.
8. **Stock & Inventory** — cover + effective cover (stock + 75% of incoming) + urgency index.
9. **Executive Report** — aggregated decisions from the same engines.

## Updating data later

Edit any file under `backend/data/`. Then either restart the API or call:

```
POST http://localhost:8000/api/reload-data
```

No frontend rebuild required.
```
