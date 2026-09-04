"""
FreightOne Backend — SIH 2026
=============================
Modular FastAPI application. All operational data lives in backend/data/*.json
so that real feeds can be swapped in later without touching business logic.

Run:
  uvicorn main:app --reload --port 8000
"""

from __future__ import annotations
from datetime import date
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from services.weather_service import weather_service
from services.data_loader import (
    managers, materials, plants, consignments as load_consignments,
    source_ports, destination_ports, cargo_prices, news_feed, reload_all
)
from services.bdi_forecast import forecast_bdi
from services.risk_analyzer import network_risk_score, full_weather_payload
from services.route_optimizer import rank_ports, procurement_plan, evaluate_route

app = FastAPI(
    title="FreightOne API",
    version="4.0.0",
    description="Intelligent Freight Forecasting & Vessel Chartering — East Coast India",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class LoginIn(BaseModel):
    user_id: str
    password: str


class RouteIn(BaseModel):
    material: str = "coking_coal"
    quantity_mt: float = 80000
    deadline_days: float = 21
    port: Optional[str] = "paradip"
    origin: Optional[str] = None
    plant_code: str = "RSP"
    priority: float = Field(55, ge=0, le=100)


class WhatIfIn(BaseModel):
    material: str = "coking_coal"
    quantity_mt: float = 80000
    deadline_days: float = 21
    port: str = "paradip"
    origin: Optional[str] = None
    plant_code: str = "RSP"
    priority: float = 55
    alt_port: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.post("/api/login")
def login(body: LoginIn):
    for m in managers():
        if m["user_id"] == body.user_id and m["password"] == body.password:
            plant = plants().get(m["plant_code"], {})
            return {
                "manager": {
                    "id": m["id"],
                    "user_id": m["user_id"],
                    "name": m["name"],
                    "employee_id": m["employee_id"],
                    "post": m["post"],
                    "rank": m["rank"],
                    "plant": m["plant_code"],
                    "posting_place": m["posting_place"],
                },
                "plant": {
                    "code": plant.get("code", m["plant_code"]),
                    "name": plant.get("name", m["plant_name"]),
                    "location": plant.get("location"),
                    "nearest_port": plant.get("nearest_port"),
                    "state": plant.get("state"),
                },
            }
    raise HTTPException(status_code=401, detail="Invalid Manager ID or password")


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

@app.get("/api/refs")
def refs():
    mats = {
        k: {
            "name": v["name"],
            "daily_consumption": v["typical_daily_consumption"],
            "safety_days": v["safety_days"],
        }
        for k, v in materials().items()
    }
    origins = {
        k: {
            "label": v["country"],
            "typical_transit_days": v["typical_transit_days_to_east_coast"],
        }
        for k, v in source_ports().items()
    }
    ports = {
        k: {"name": v["name"], "state": v["state"]}
        for k, v in destination_ports().items()
    }
    pls = {
        k: {
            "name": v["name"],
            "nearest_port": v["nearest_port"],
            "state": v["state"],
        }
        for k, v in plants().items()
    }
    return {"materials": mats, "origins": origins, "ports": ports, "plants": pls}


# ---------------------------------------------------------------------------
# BDI / Freight intelligence
# ---------------------------------------------------------------------------

@app.get("/api/forecast")
def api_forecast(horizon: int = Query(90, ge=30, le=120)):
    return forecast_bdi(horizon)


@app.get("/api/freight-intelligence")
def freight_intelligence():
    fc = forecast_bdi(90)
    return {
        "forecast": {
            "history": fc["history"],
            "forecast": fc["forecast"],
        },
        "booking_window": fc["booking_window"],
        "indices": fc["indices"],
        "model": fc["model"],
    }


# ---------------------------------------------------------------------------
# Risk & Weather
# ---------------------------------------------------------------------------

@app.get("/api/risk-score")
def risk_score():
    return network_risk_score()


@app.get('/api/weather')
def weather():
    # Retrieves the live report (automatically manages the 2-hour update refresh)
    return weather_service.get_weather_report()


@app.get("/api/news")
def news():
    return news_feed()


# ---------------------------------------------------------------------------
# Consignments
# ---------------------------------------------------------------------------

@app.get("/api/consignments")
def consignments(plant_code: Optional[str] = None, status: Optional[str] = None):
    items = load_consignments().get("items", [])
    if plant_code:
        items = [c for c in items if c.get("plant_code") == plant_code]
    if status:
        items = [c for c in items if str(c.get("status", "")).lower() == status.lower()]
    return {"consignments": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Inventory & urgency
# ---------------------------------------------------------------------------

@app.get("/api/inventory")
def inventory(plant_code: str = "RSP"):
    plant = plants().get(plant_code)
    if not plant:
        raise HTTPException(404, "Plant not found")
    mats = materials()
    cons = load_consignments().get("items", [])
    out = []
    for mid, m in mats.items():
        inv = plant.get("inventory", {}).get(mid, {})
        stock = inv.get("stock_mt", 0)
        daily = m["typical_daily_consumption"]
        cover = stock / daily if daily else 0
        incoming = sum(
            c["tonnage"]
            for c in cons
            if c.get("plant_code") == plant_code
            and c.get("material") == mid
            and str(c.get("status", "")).lower() not in ("delivered",)
        )
        # future + active reduce urgency
        effective = (stock + incoming * 0.75) / daily if daily else 0
        urgency = min(10, max(1, round(14 - effective)))
        if effective < m.get("safety_days", 6):
            urgency = max(urgency, 7)
        rating = "Critical" if urgency >= 8 else "Watch" if urgency >= 5 else "Healthy"
        out.append({
            "id": mid,
            "material": m["name"],
            "stock_mt": stock,
            "daily_consumption": daily,
            "days_cover": round(cover, 1),
            "effective_cover": round(effective, 1),
            "incoming_mt": incoming,
            "urgency_index": urgency,
            "rating": rating,
            "safety_days": m.get("safety_days", 6),
        })
    return {"plant": plant["name"], "plant_code": plant_code, "items": out}


# ---------------------------------------------------------------------------
# Alerts (derived, not static)
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
def alerts(plant_code: str = "RSP"):
    alerts_list = []
    # Delayed consignments
    for c in load_consignments().get("items", []):
        if str(c.get("status", "")).lower() == "delayed":
            alerts_list.append({
                "severity": "high",
                "type": "CONSIGNMENT",
                "title": f"{c['id']} is delayed by {c.get('delay_days', 0)} days",
                "impact": f"{c.get('material_label', c.get('material'))} supply exposure for {c.get('plant_code')}",
                "action": "Open recovery / reroute recommendation",
                "ref": c["id"],
            })
    # Weather
    risk = network_risk_score()
    if risk["risk_level"] in ("amber", "red"):
        alerts_list.append({
            "severity": "medium" if risk["risk_level"] == "amber" else "high",
            "type": "WEATHER",
            "title": "Bay of Bengal weather risk elevated",
            "impact": f"Network risk score {risk['risk_score']}/100",
            "action": "Monitor vessel ETAs and berth windows",
        })
    # Market / BDI
    fc = forecast_bdi(30)
    trend = fc["forecast"][14]["bdi"] - fc["history"][-1]["bdi"]
    if trend > 40:
        alerts_list.append({
            "severity": "medium",
            "type": "MARKET",
            "title": "BDI trend remains upward",
            "impact": "Future charter cost sensitivity over next 2 weeks",
            "action": "Review booking window before further firming",
        })
    # Inventory
    inv = inventory(plant_code)["items"]
    for item in inv:
        if item["urgency_index"] >= 8:
            alerts_list.append({
                "severity": "high",
                "type": "INVENTORY",
                "title": f"{item['material']} cover is critical",
                "impact": f"Only {item['days_cover']} days of cover at plant",
                "action": "Trigger procurement planner",
            })
    return {"alerts": alerts_list}


# ---------------------------------------------------------------------------
# Procurement planner
# ---------------------------------------------------------------------------

@app.post("/api/procurement")
def procurement(body: RouteIn):
    try:
        plan = procurement_plan(
            material=body.material,
            quantity_mt=body.quantity_mt,
            deadline_days=body.deadline_days,
            preferred_port=body.port,
            plant_code=body.plant_code,
            priority=body.priority,
        )
        return plan
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/route-options")
def route_options(body: RouteIn):
    ranking = rank_ports(
        material=body.material,
        plant_code=body.plant_code,
        quantity_mt=body.quantity_mt,
        origin=body.origin,
        priority_cost=body.priority,
        deadline_days=body.deadline_days,
    )
    selected = None
    if body.port:
        for o in ranking["options"]:
            if o["port"] == body.port:
                selected = o
                break
    return {
        "selected_port": selected or ranking.get("best"),
        "best_overall": ranking.get("best"),
        "options": ranking.get("options", []),
        "weights": ranking.get("weights"),
    }


# ---------------------------------------------------------------------------
# Port optimiser (same ranking engine)
# ---------------------------------------------------------------------------

@app.post("/api/optimizer")
def optimizer(body: RouteIn):
    ranking = rank_ports(
        material=body.material,
        plant_code=body.plant_code,
        quantity_mt=body.quantity_mt,
        origin=body.origin,
        priority_cost=body.priority,
        deadline_days=body.deadline_days,
    )
    return {
        "material": body.material,
        "plant_code": body.plant_code,
        "ranked": ranking["options"][:8],
        "best": ranking["best"],
        "weights": ranking["weights"],
    }


# ---------------------------------------------------------------------------
# What-if
# ---------------------------------------------------------------------------

@app.post("/api/what-if")
def what_if(body: WhatIfIn):
    base_plan = procurement_plan(
        material=body.material,
        quantity_mt=body.quantity_mt,
        deadline_days=body.deadline_days,
        preferred_port=body.port,
        plant_code=body.plant_code,
        priority=body.priority,
    )
    base = base_plan["selected"]
    best = base_plan["best_overall"]

    # Optional forced alternative
    alt = None
    if body.alt_port and body.alt_port != body.port:
        try:
            alt = evaluate_route(
                body.material,
                body.origin or (best["origin"] if best else "australia"),
                body.alt_port,
                body.plant_code,
                body.quantity_mt,
                body.priority,
            )
        except Exception:
            alt = None
    if alt is None:
        alt = best

    if not base or not alt:
        raise HTTPException(400, "Unable to build comparison scenarios")

    return {
        "base": base,
        "what_if": alt,
        "difference": {
            "cost_delta": alt["total_cost"] - base["total_cost"],
            "eta_delta_days": round(alt["eta_days"] - base["eta_days"], 1),
            "risk_delta": alt["risk_score"] - base["risk_score"],
        },
        "summary": (
            "Comparison uses live cargo prices, distance-derived freight, "
            "port congestion and inland rail rates. Preferred choice vs best "
            "available alternative under the same constraints."
        ),
    }


# ---------------------------------------------------------------------------
# Executive report
# ---------------------------------------------------------------------------

@app.get("/api/executive-report")
def executive_report(plant_code: str = "RSP"):
    risk = network_risk_score()
    cons = load_consignments().get("items", [])
    active = [c for c in cons if str(c.get("status", "")).lower() not in ("delivered", "future")]
    delayed = [c for c in cons if str(c.get("status", "")).lower() == "delayed"]
    inv = inventory(plant_code)["items"]
    watch = sum(1 for i in inv if i["urgency_index"] >= 5)

    decisions = []
    for c in delayed:
        decisions.append(f"Review recovery path for {c['id']} ({c.get('delay_days')}d late)")
    for i in inv:
        if i["urgency_index"] >= 8:
            decisions.append(f"Prioritise {i['material']} booking — cover critical")
    if risk["risk_level"] != "green":
        decisions.append("Maintain heightened watch on Bay of Bengal weather & ETAs")
    fc = forecast_bdi(30)
    if fc["booking_window"]["expected_savings_percent"] >= 3:
        decisions.append(
            f"Consider freight booking window around day {fc['booking_window']['best_day']} "
            f"(~{fc['booking_window']['expected_savings_percent']}% rate relief)"
        )
    if not decisions:
        decisions.append("No critical actions — continue routine monitoring")

    return {
        "summary": {
            "network_risk": risk["risk_score"],
            "active_consignments": len(active),
            "delayed_consignments": len(delayed),
            "inventory_watch": watch,
        },
        "decisions": decisions[:6],
        "generated_on": date.today().isoformat(),
        "plant": plants().get(plant_code, {}).get("name", plant_code),
    }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

@app.post("/api/reload-data")
def reload_data():
    """Force re-read of all JSON data files (useful after manual updates)."""
    reload_all()
    return {"status": "ok", "message": "Data cache cleared"}


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "FreightOne", "version": "4.0.0"}
