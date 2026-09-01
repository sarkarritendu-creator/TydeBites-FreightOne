"""
Port & Route Optimiser + Procurement cost engine
------------------------------------------------
Uses:
  - source_ports (lat/lon + typical transit)
  - destination_ports (draft, congestion, historic preference, inland links)
  - cargo_prices (FOB)
  - inland_transport
  - BDI / risk for freight estimate

Scoring formula (explainable):
  total_score = w_cost * norm_cost + w_time * norm_time + w_risk * norm_risk
                - w_hist * historic_preference

Lower total_score is better. Weights can be shifted by the manager's
cost-vs-deadline priority slider.
"""

from __future__ import annotations
from datetime import date, timedelta
from typing import Dict, List, Optional, Any
from .data_loader import (
    materials, source_ports, destination_ports, cargo_prices,
    inland_transport, plants, consignments
)
from .geo import haversine_nm, estimate_sea_days
from .bdi_forecast import forecast_bdi
from .risk_analyzer import network_risk_score


def _freight_rate_usd_mt(origin_key: str, dest_key: str, material: str, bdi: float) -> float:
    """Very rough voyage freight estimate from distance + BDI level."""
    src = source_ports().get(origin_key)
    dst = destination_ports().get(dest_key)
    if not src or not dst:
        return 18.0
    dist = haversine_nm(src["lat"], src["lon"], dst["lat"], dst["lon"])
    # Base rate scales with BDI; longer hauls higher
    base = (bdi / 1400.0) * (8.0 + dist / 900.0)
    # material adjustment
    if material in ("coking_coal", "thermal_coal"):
        base *= 1.05
    if material == "iron_ore":
        base *= 0.95
    return round(max(6.0, base), 2)


def _inland_for(port_code: str, plant_code: str) -> Dict:
    key = f"{port_code}_to_{plant_code}"
    data = inland_transport()
    if key in data:
        return data[key]
    # fallback from destination_ports
    port = destination_ports().get(port_code, {})
    link = port.get("inland_to_plants", {}).get(plant_code)
    if link:
        return {
            "rail_transit_days": link.get("rail_days", 3),
            "rail_rate_inr_mt": link.get("rail_rate_per_mt", 450),
            "rail_distance_km": link.get("distance_km", 500),
        }
    return {"rail_transit_days": 4, "rail_rate_inr_mt": 500, "rail_distance_km": 600}


def evaluate_route(
    material: str,
    origin: str,
    port: str,
    plant_code: str,
    quantity_mt: float,
    priority_cost: float = 50.0,
) -> Dict[str, Any]:
    """
    priority_cost: 0 = pure deadline, 100 = pure cost.
    Returns a full cost / time / risk breakdown for one origin-port-plant path.
    """
    mat = materials().get(material, {})
    src = source_ports().get(origin, {})
    dst = destination_ports().get(port, {})
    prices = cargo_prices().get(material, {})
    fob = prices.get(origin, {}).get("inr_mt")
    if fob is None:
        # try USD conversion
        usd = prices.get(origin, {}).get("fob_usd_mt", 100)
        fob = usd * cargo_prices().get("fx_usd_inr", 84.0)

    bdi = forecast_bdi(5)["indices"]["BDI"]
    freight_usd = _freight_rate_usd_mt(origin, port, material, bdi)
    freight_inr = freight_usd * cargo_prices().get("fx_usd_inr", 84.0)

    inland = _inland_for(port, plant_code)
    inland_inr = inland.get("rail_rate_inr_mt", 450)

    # Simple duty / handling approximation
    handling_inr = 180 + dst.get("avg_queue_days", 2) * 25

    total_per_mt = fob + freight_inr + inland_inr + handling_inr
    total_cost = total_per_mt * quantity_mt

    # Time
    sea_days = src.get("typical_transit_days_to_east_coast")
    if sea_days is None and src:
        dist = haversine_nm(src["lat"], src["lon"], dst["lat"], dst["lon"])
        sea_days = estimate_sea_days(dist)
    sea_days = float(sea_days or 18)
    queue = float(dst.get("avg_queue_days", 2))
    inland_days = float(inland.get("rail_transit_days", 3))
    eta_days = sea_days + queue + inland_days + 1.5  # buffer

    # Risk
    base_risk = network_risk_score()["risk_score"]
    port_risk = min(40, dst.get("avg_queue_days", 2) * 8)
    hist = dst.get("historic_preference", {}).get(material, 0.2)
    # higher historic preference slightly lowers risk score for this route
    risk_score = max(5, min(95, base_risk * 0.6 + port_risk + (1 - hist) * 15))

    # Draft / capability feasibility
    capable = material in dst.get("handling_capability", [])
    draft_ok = True  # simplified; real check would use vessel DWT

    return {
        "material": material,
        "material_label": mat.get("name", material),
        "origin": origin,
        "origin_label": src.get("country", origin),
        "port": port,
        "port_label": dst.get("name", port),
        "plant_code": plant_code,
        "quantity_mt": quantity_mt,
        "fob_inr_mt": round(fob, 1),
        "freight_inr_mt": round(freight_inr, 1),
        "inland_inr_mt": round(inland_inr, 1),
        "handling_inr_mt": round(handling_inr, 1),
        "total_cost_mt": round(total_per_mt, 1),
        "total_cost": round(total_cost),
        "sea_days": round(sea_days, 1),
        "queue_days": queue,
        "inland_days": inland_days,
        "eta_days": round(eta_days, 1),
        "risk_score": round(risk_score),
        "historic_preference": hist,
        "capable": capable,
        "draft_ok": draft_ok,
        "congestion": dst.get("typical_congestion", "Medium"),
        "max_draft_m": dst.get("max_draft_m"),
        "max_vessel_dwt": dst.get("max_vessel_dwt"),
    }


def rank_ports(
    material: str,
    plant_code: str,
    quantity_mt: float,
    origin: Optional[str] = None,
    priority_cost: float = 50.0,
    deadline_days: Optional[float] = None,
) -> Dict:
    """
    Rank all feasible destination ports (optionally constrained by origin).
    priority_cost 0..100 controls weight between cost and time.
    """
    mat = materials().get(material)
    if not mat:
        raise ValueError(f"Unknown material: {material}")

    origins = [origin] if origin else mat.get("preferred_origins", list(source_ports().keys()))
    ports = list(destination_ports().keys())

    # Weights: higher priority_cost → more weight on cost
    w_cost = priority_cost / 100.0
    w_time = 1.0 - w_cost
    w_risk = 0.25
    w_hist = 0.15

    candidates = []
    for o in origins:
        if o not in source_ports():
            continue
        for p in ports:
            try:
                r = evaluate_route(material, o, p, plant_code, quantity_mt, priority_cost)
            except Exception:
                continue
            if not r["capable"]:
                continue
            candidates.append(r)

    if not candidates:
        return {"options": [], "best": None, "selected": None}

    # Normalise for scoring
    costs = [c["total_cost_mt"] for c in candidates]
    times = [c["eta_days"] for c in candidates]
    risks = [c["risk_score"] for c in candidates]
    c_min, c_max = min(costs), max(costs) or 1
    t_min, t_max = min(times), max(times) or 1
    r_min, r_max = min(risks), max(risks) or 1

    for c in candidates:
        nc = (c["total_cost_mt"] - c_min) / (c_max - c_min + 1e-6)
        nt = (c["eta_days"] - t_min) / (t_max - t_min + 1e-6)
        nr = (c["risk_score"] - r_min) / (r_max - r_min + 1e-6)
        score = w_cost * nc + w_time * nt + w_risk * nr - w_hist * c["historic_preference"]
        if deadline_days is not None and c["eta_days"] > deadline_days:
            score += 0.35  # penalty for missing deadline
        c["score"] = round(score, 4)
        c["rank_label"] = "candidate"

    candidates.sort(key=lambda x: x["score"])
    for i, c in enumerate(candidates):
        c["rank"] = i + 1
        if i == 0:
            c["rank_label"] = "best"
        elif i == 1:
            c["rank_label"] = "alternative"

    best = candidates[0]
    return {
        "options": candidates,
        "best": best,
        "count": len(candidates),
        "weights": {"cost": w_cost, "time": w_time, "risk": w_risk, "history": w_hist},
    }


def procurement_plan(
    material: str,
    quantity_mt: float,
    deadline_days: float,
    preferred_port: Optional[str],
    plant_code: str,
    priority: float = 55.0,
) -> Dict:
    """Full planner response used by the Procurement Planner screen."""
    ranking = rank_ports(
        material=material,
        plant_code=plant_code,
        quantity_mt=quantity_mt,
        priority_cost=priority,
        deadline_days=deadline_days,
    )
    options = ranking["options"]
    best = ranking["best"]

    selected = None
    if preferred_port:
        for o in options:
            if o["port"] == preferred_port:
                selected = o
                break
    if selected is None and options:
        selected = options[0]

    # Inventory / urgency context
    plant = plants().get(plant_code, {})
    inv = plant.get("inventory", {}).get(material, {})
    stock = inv.get("stock_mt", 0)
    safety = inv.get("safety_stock_mt", 0)
    daily = materials().get(material, {}).get("typical_daily_consumption", 5000)
    cover = stock / daily if daily else 0

    # Incoming from active consignments
    cons = consignments().get("items", [])
    incoming = sum(
        c["tonnage"]
        for c in cons
        if c.get("plant_code") == plant_code
        and c.get("material") == material
        and str(c.get("status", "")).lower() not in ("delivered", "future")
    )
    effective_cover = (stock + incoming * 0.7) / daily if daily else 0

    urgency = min(10, max(1, round(12 - effective_cover)))
    if effective_cover < materials().get(material, {}).get("safety_days", 6):
        urgency = max(urgency, 8)

    ai_tile = {
        "preferred_port": best["port_label"] if best else None,
        "preferred_port_code": best["port"] if best else None,
        "origin_label": best["origin_label"] if best else None,
        "quantity_mt": quantity_mt,
        "urgency_index": urgency,
        "days_of_cover": round(effective_cover, 1),
        "stock_mt": stock,
        "incoming_mt": incoming,
        "recommendation": (
            "Place order soon — cover below safety buffer."
            if urgency >= 8
            else "Monitor — cover adequate but freight window matters."
            if urgency >= 5
            else "No immediate action required on volume; optimise rate."
        ),
    }

    return {
        "selected": selected,
        "best_overall": best,
        "options": options[:6],
        "ai": ai_tile,
        "deadline_days": deadline_days,
        "priority": priority,
        "plant": plant.get("name", plant_code),
    }
