from __future__ import annotations
import json, math
from pathlib import Path
from typing import Any, Dict, Optional
from services.data_loader import destination_ports, source_ports

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def _load_vessels():
    with open(DATA_DIR / "vessel_optimizer_data.json", "r", encoding="utf-8") as f:
        return json.load(f).get("vessels", [])

def _ports():
    return destination_ports()

def _port(port_id: str):
    ports = _ports(); key = str(port_id or "").strip().lower()
    aliases = {"visakhapatnam":"vizag", "visakhapatnam port":"vizag", "paradip port":"paradip", "gangavaram port":"gangavaram", "haldia port":"haldia"}
    key = aliases.get(key,key)
    if key in ports: return key, ports[key]
    for k,v in ports.items():
        if str(v.get("name","")).lower() == key: return k,v
    raise ValueError(f"Destination port '{port_id}' not found")

def _origin(origin: Optional[str]):
    data=source_ports()
    row=data.get(origin or "", {})
    return {"transit_days": float(row.get("typical_transit_days_to_east_coast",16)), "rate_multiplier": float(row.get("base_sea_rate_multiplier",1.0)), "label": row.get("country", origin or "Selected origin")}

def _score_norm(value, low, high):
    if high-low <= 1e-9: return 1.0
    return max(0.0,min(1.0,(high-value)/(high-low)))

def optimize_vessels(port="paradip", quantity_mt=80000, deadline_days=30, origin="australia", material="coking_coal", priority=55, **kwargs):
    port_id,p=_port(port); origin_row=_origin(origin)
    qty=max(1,float(quantity_mt)); deadline=max(1,float(deadline_days)); priority=max(0,min(100,float(priority)))
    max_draft=float(p.get("max_draft_m",0)); max_dwt=float(p.get("max_vessel_dwt",0))
    # Existing destination_ports.json has no LOA/beam fields. Keep those optional
    # so the optimizer never invents zeros as physical limits.
    with open(DATA_DIR / "vessel_optimizer_data.json", "r", encoding="utf-8") as f:
        vessel_ref = json.load(f)
    berth = (vessel_ref.get("port_constraints", {}) or {}).get(port_id, {})
    max_loa = float(berth.get("max_loa_m", 0))
    max_beam = float(berth.get("max_beam_m", 0))
    handling=max(1,float(p.get("handling_rate_mt_per_day",30000)))
    queue_days=max(0,float(p.get("avg_queue_days",0))); berths=max(1,float(p.get("berth_capacity",1)))
    all_rows=[]
    for v in _load_vessels():
        cap=float(v["capacity_mt"]); dwt=float(v.get("dwt_mt",cap)); draft=float(v["draft_m"]); loa=float(v.get("loa_m",0)); beam=float(v.get("beam_m",0)); speed=max(1,float(v.get("speed_knots",13))); sea_rate=float(v.get("sea_rate_per_mt",0)); charter=float(v.get("charter_usd_day",0))
        reasons=[]
        fits={"draft": True, "dwt": True, "loa": True, "beam": True}
        if max_draft and draft>max_draft: fits["draft"]=False; reasons.append(f"Draft {draft:.1f} m > {max_draft:.1f} m port limit")
        if max_dwt and dwt>max_dwt: fits["dwt"]=False; reasons.append(f"DWT {dwt:,.0f} > {max_dwt:,.0f} port limit")
        if max_loa and loa>max_loa: fits["loa"]=False; reasons.append(f"LOA {loa:.0f} m > {max_loa:.0f} m berth limit")
        if max_beam and beam>max_beam: fits["beam"]=False; reasons.append(f"Beam {beam:.1f} m > {max_beam:.1f} m berth limit")
        feasible=not reasons
        trips=max(1,math.ceil(qty/cap))
        util=qty/(trips*cap)*100
        sailing=origin_row["transit_days"]*13/speed
        unload=(trips*cap)/handling
        queue=queue_days*(trips/berths)
        eta=sailing+unload+queue
        sea_cost=qty*sea_rate*origin_row["rate_multiplier"]
        charter_cost=charter*eta*trips
        handling_cost=qty*0.22
        total=sea_cost+charter_cost+handling_cost
        all_rows.append({"vessel":v["name"],"vessel_class":v["class"],"capacity_mt":round(cap),"dwt":round(dwt),"draft_m":draft,"loa_m":loa,"beam_m":beam,"shipments_needed":trips,"utilisation_pct":round(util,1),"sailing_days":round(sailing,1),"port_turnaround_days":round(unload+queue,1),"eta_days":round(eta,1),"sea_cost":round(sea_cost),"charter_cost":round(charter_cost),"handling_cost":round(handling_cost),"total_cost":round(total),"cost_per_mt":round(total/qty,2),"feasible":feasible,"reason":"Fits all configured port constraints." if feasible else "; ".join(reasons),"fit":fits})
    feasible=[x for x in all_rows if x["feasible"]]; rejected=[x for x in all_rows if not x["feasible"]]
    if feasible:
        costs=[x["cost_per_mt"] for x in feasible]; etas=[x["eta_days"] for x in feasible]; minc,maxc=min(costs),max(costs)
        for x in feasible:
            cost_component=_score_norm(x["cost_per_mt"],minc,maxc)
            deadline_component=1 if x["eta_days"]<=deadline else max(0,1-(x["eta_days"]-deadline)/deadline)
            util_component=max(0,1-abs(x["utilisation_pct"]-85)/85)
            x["optimization_score"]=round(max(0,min(100,(1-priority/100)*50*cost_component + (priority/100)*35*deadline_component + 15*util_component)),1)
        feasible.sort(key=lambda x:(-x["optimization_score"],x["cost_per_mt"],x["eta_days"]))
        for i,x in enumerate(feasible,1): x["rank"]=i
    for x in rejected: x["optimization_score"]=0.0; x["rank"]=None
    ranked=feasible+rejected
    return {"port":p.get("name",port_id),"port_id":port_id,"material":material,"origin":origin,"quantity_mt":qty,"deadline_days":deadline,"priority":priority,"best":feasible[0] if feasible else None,"ranked":ranked,"options":feasible,"rejected":rejected,"feasible_count":len(feasible),"port_constraints":{"max_draft_m":max_draft or None,"max_dwt":max_dwt or None,"max_loa_m":max_loa or None,"max_beam_m":max_beam or None,"handling_rate_mt_per_day":handling,"ships_in_queue":p.get("ships_in_queue",0),"berths":p.get("berths", p.get("berth_capacity", 0)),"avg_queue_days":queue_days,"typical_congestion":p.get("typical_congestion","—")},"vessel_fits":[{"vessel":x["vessel"],"vessel_class":x["vessel_class"],"feasible":x["feasible"],"reason":x["reason"],"fit":x["fit"],"draft_m":x["draft_m"],"loa_m":x["loa_m"],"beam_m":x["beam_m"],"dwt":x["dwt"]} for x in ranked],"explainability":{"port_fixed":True,"summary":"Port is held constant. Physical berth constraints are screened first; feasible vessels are then ranked using vessel-specific sea rate, charter time, congestion, ETA and cargo utilisation."}}

optimise_vessels=optimize_vessels
