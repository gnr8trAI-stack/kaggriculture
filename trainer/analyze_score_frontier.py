"""Analyze the real Kaggriculture score frontier from replay trajectories.

This is a descriptive research tool, not a policy learner. It answers one
question before we design a >200k agent: what do the highest-scoring real farms
actually look like?

Inputs
------
- replay_db/index.csv produced by trainer/ingest_replays.py
- source replay JSON/JSON.GZ files referenced by the index

Outputs
-------
- frontier_summary.json: corpus score distribution + threshold counts
- frontier_top_trajectories.csv: top-N trajectories and compact features
- frontier_daily_curves.csv: day snapshots for top trajectories
- frontier_action_mix.csv: action counts for top trajectories

The analyzer does not use outer/fit windows for selection; it studies the whole
resolved corpus because this is frontier reconnaissance, not training.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping

CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
ANIMALS=("GOOSE","COW","SHEEP")


def _m(v: Any) -> Mapping[str, Any]:
    return v if isinstance(v, Mapping) else {}


def _episode_id(value: Mapping[str, Any]) -> str:
    for container in (value,_m(value.get("metadata")),_m(value.get("info"))):
        for key in ("episodeId","episode_id","id"):
            item=container.get(key)
            if item not in (None,""):
                return str(item)
    return ""


def _find_episode(value: Any, eid: str):
    if isinstance(value, Mapping):
        steps=value.get("steps")
        if isinstance(steps,list) and steps:
            found=_episode_id(value)
            if not eid or found in {"",eid}:
                return value
        for child in value.values():
            hit=_find_episode(child,eid)
            if hit is not None:
                return hit
    elif isinstance(value,list):
        for child in value:
            hit=_find_episode(child,eid)
            if hit is not None:
                return hit
    return None


def _load(path: Path, eid: str):
    try:
        if path.suffix.lower()==".gz":
            with gzip.open(path,"rt",encoding="utf-8") as f:
                data=json.load(f)
        else:
            data=json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None
    return _find_episode(data,eid)


def _tile_features(obs: Mapping[str,Any], seat: int) -> Dict[str,Any]:
    farms=obs.get("farms") or []
    farm=_m(farms[seat]) if isinstance(farms,list) and seat<len(farms) else {}
    crops=Counter(); animals=Counter(); weeds=occupied=usable=0
    for row in farm.get("tiles") or []:
        if not isinstance(row,list): continue
        for tile in row:
            if tile=="LOCKED": continue
            kind=str(_m(tile).get("kind","")).upper() if isinstance(tile,Mapping) else ""
            if kind=="LOCKED": continue
            usable+=1
            if tile is not None: occupied+=1
            if kind=="WEED": weeds+=1
            elif kind=="PLANT":
                crop=str(_m(tile).get("crop","")).upper()
                if crop: crops[crop]+=1
            elif kind in {"COOP","PASTURE"}:
                animal=str(_m(tile).get("animal","")).upper()
                if animal: animals[animal]+=1
    land=farm.get("unlocked_quadrants") or ["NW"]
    return {
        "money":float(farm.get("money",0) or 0),
        "hands":len(farm.get("hands") or []),
        "land":len(land),
        "usable":usable,
        "occupied":occupied,
        "weeds":weeds,
        "weed_ratio":weeds/max(1,usable),
        "crop_total":sum(crops.values()),
        "animal_total":sum(animals.values()),
        **{f"crop_{c}":crops[c] for c in CROPS},
        **{f"animal_{a}":animals[a] for a in ANIMALS},
    }


def _count_action(counter: Counter, action: Mapping[str,Any]):
    farmer=action.get("farmer")
    actor=[]
    if isinstance(farmer,list) and farmer: actor.append(farmer)
    for hand in action.get("hands") or []:
        if isinstance(hand,list) and hand: actor.append(hand)
    for a in actor:
        op=str(a[0]).upper(); counter[op]+=1
        if op=="PLANT" and len(a)>1: counter[f"PLANT_{str(a[1]).upper()}"]+=1
    for mk in action.get("market") or []:
        if not isinstance(mk,list) or not mk: continue
        op=str(mk[0]).upper(); counter[op]+=1
        if op in {"BUY_ANIMAL","BUY_SEED","BUY_PRODUCT","SELL"} and len(mk)>1:
            counter[f"{op}_{str(mk[1]).upper()}"]+=1
            if len(mk)>2:
                try: counter[f"{op}_{str(mk[1]).upper()}_UNITS"]+=int(mk[2])
                except Exception: pass


def _trajectory(ep: Mapping[str,Any], seat: int) -> Dict[str,Any]:
    daily: Dict[int,Dict[str,Any]]={}
    daily_max_hands=Counter()
    actions=Counter()
    first_land_day=None; first_animal_day=None
    peak_money=0.0; peak_land=1; peak_animals=0; peak_crops=0; max_weed=0.0
    for step in ep.get("steps") or []:
        if not isinstance(step,list) or seat>=len(step): continue
        entry=_m(step[seat]); obs=_m(entry.get("observation"))
        if obs:
            day=int(obs.get("day",0) or 0)
            feat=_tile_features(obs,seat)
            daily[day]=feat  # final observation seen for the day
            daily_max_hands[day]=max(daily_max_hands[day],int(feat["hands"]))
            peak_money=max(peak_money,float(feat["money"]))
            peak_land=max(peak_land,int(feat["land"]))
            peak_animals=max(peak_animals,int(feat["animal_total"]))
            peak_crops=max(peak_crops,int(feat["crop_total"]))
            max_weed=max(max_weed,float(feat["weed_ratio"]))
            if first_land_day is None and int(feat["land"])>=2: first_land_day=day
            if first_animal_day is None and int(feat["animal_total"])>=1: first_animal_day=day
        _count_action(actions,_m(entry.get("action")))
    for day,feat in daily.items(): feat["max_hands_day"]=daily_max_hands[day]
    return {
        "daily":daily,"actions":actions,
        "first_land_day":first_land_day,"first_animal_day":first_animal_day,
        "peak_money":peak_money,"peak_land":peak_land,"peak_animals":peak_animals,
        "peak_crops":peak_crops,"max_weed_ratio":max_weed,
    }


def _q(values,p):
    vals=sorted(float(v) for v in values)
    if not vals: return 0.0
    if len(vals)==1: return vals[0]
    x=(len(vals)-1)*p; lo=math.floor(x); hi=math.ceil(x)
    if lo==hi:return vals[lo]
    return vals[lo]+(vals[hi]-vals[lo])*(x-lo)


def analyze(corpus: Path, output: Path, top_n: int=50):
    rows=list(csv.DictReader((corpus/"index.csv").open(encoding="utf-8")))
    resolved=[r for r in rows if r.get("identity_source")!="unresolved" and r.get("reward") not in (None,"")]
    rewards=[float(r["reward"]) for r in resolved]
    ranked=sorted(resolved,key=lambda r:float(r["reward"]),reverse=True)[:top_n]
    output.mkdir(parents=True,exist_ok=True)

    top_rows=[]; curve_rows=[]; action_rows=[]
    for rank,row in enumerate(ranked,1):
        eid=str(row.get("episode_id") or ""); seat=int(row.get("seat") or 0)
        path=Path(str(row.get("source") or ""))
        if not path.exists():
            fallback=corpus/"episodes"/f"{eid}.json.gz"
            path=fallback if fallback.exists() else path
        ep=_load(path,eid)
        if ep is None: continue
        t=_trajectory(ep,seat)
        top_rows.append({
            "rank":rank,"episode_id":eid,"seat":seat,"team":row.get("team","") or row.get("submission_id",""),
            "reward":float(row["reward"]),"opponent_reward":float(row.get("opponent_reward") or 0),
            "result":row.get("result",""),"window":row.get("window",""),
            "first_land_day":t["first_land_day"],"first_animal_day":t["first_animal_day"],
            "peak_land":t["peak_land"],"peak_animals":t["peak_animals"],"peak_crops":t["peak_crops"],
            "peak_money":t["peak_money"],"max_weed_ratio":round(t["max_weed_ratio"],4),
        })
        for day,feat in sorted(t["daily"].items()):
            curve_rows.append({"rank":rank,"episode_id":eid,"seat":seat,"reward":float(row["reward"]),"day":day,**feat})
        action_rows.append({
            "rank":rank,"episode_id":eid,"seat":seat,"reward":float(row["reward"]),
            **{k:int(v) for k,v in sorted(t["actions"].items())},
        })

    def write_csv(path,rows):
        if not rows: return
        fields=[]; seen=set()
        for row in rows:
            for k in row:
                if k not in seen: seen.add(k); fields.append(k)
        with path.open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)

    write_csv(output/"frontier_top_trajectories.csv",top_rows)
    write_csv(output/"frontier_daily_curves.csv",curve_rows)
    write_csv(output/"frontier_action_mix.csv",action_rows)

    thresholds=(50000,75000,100000,125000,150000,175000,200000,250000)
    summary={
        "resolved_trajectories":len(resolved),
        "max_reward":max(rewards) if rewards else 0,
        "p50_reward":_q(rewards,.50),"p90_reward":_q(rewards,.90),"p95_reward":_q(rewards,.95),
        "p99_reward":_q(rewards,.99),"p999_reward":_q(rewards,.999),
        "threshold_counts":{str(x):sum(v>=x for v in rewards) for x in thresholds},
        "threshold_rates":{str(x):round(sum(v>=x for v in rewards)/max(1,len(rewards)),6) for x in thresholds},
        "top_n_requested":top_n,"top_n_parsed":len(top_rows),
        "frontier_top10":top_rows[:10],
    }
    (output/"frontier_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--corpus",type=Path,default=Path("replay_db")); p.add_argument("--output",type=Path,default=Path("artifacts/frontier")); p.add_argument("--top-n",type=int,default=50)
    a=p.parse_args(); analyze(a.corpus,a.output,a.top_n)
