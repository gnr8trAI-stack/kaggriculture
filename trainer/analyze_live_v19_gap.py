"""Analyze the current live V19 Kaggriculture submission against fresh public replays.

The script identifies our team from the downloaded leaderboard/current rank, then
finds that team's trajectories in a freshly harvested replay index. It compares
our recent games with the strongest contemporaneous trajectories and emits a
small machine-readable diagnosis for two-shot live iteration.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from trainer.analyze_score_frontier import _load, _trajectory


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def rows(path: Path):
    if not path.exists() or not path.stat().st_size:
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(v: Any, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def percentile(vals, p):
    vals=sorted(float(x) for x in vals)
    if not vals: return 0.0
    if len(vals)==1: return vals[0]
    x=(len(vals)-1)*p; lo=math.floor(x); hi=math.ceil(x)
    if lo==hi: return vals[lo]
    return vals[lo]+(vals[hi]-vals[lo])*(x-lo)


def pick_col(row, *names):
    wanted={norm(n) for n in names}
    for k,v in row.items():
        if norm(k) in wanted:
            return v
    return ""


def infer_team(leaderboard_dir: Path, current_rank: int, live_score: float) -> dict:
    csvs=list(leaderboard_dir.rglob("*.csv"))
    allrows=[]
    for p in csvs:
        try: allrows.extend(rows(p))
        except Exception: pass
    candidates=[]
    for i,r in enumerate(allrows,1):
        team=str(pick_col(r,"teamName","team","name"))
        score=fnum(pick_col(r,"score","publicScore"),-1)
        rankv=int(fnum(pick_col(r,"rank","userRank"),i))
        if team:
            candidates.append({"team":team,"score":score,"rank":rankv,"ordinal":i})
    by_rank=[x for x in candidates if x["rank"]==current_rank]
    by_score=sorted(candidates,key=lambda x:abs(x["score"]-live_score))[:5]
    chosen=None
    if by_rank:
        chosen=min(by_rank,key=lambda x:abs(x["score"]-live_score))
    elif 1 <= current_rank <= len(candidates):
        chosen=candidates[current_rank-1]
    elif by_score and abs(by_score[0]["score"]-live_score)<0.2:
        chosen=by_score[0]
    return {"chosen":chosen,"score_neighbors":by_score,"rows":len(candidates)}


def compact(row, traj):
    daily=traj["daily"]
    def d(day,key,default=0):
        return daily.get(day,{}).get(key,default)
    return {
        "episode_id":row.get("episode_id",""),"seat":int(row.get("seat") or 0),
        "reward":fnum(row.get("reward")),"opponent_reward":fnum(row.get("opponent_reward")),
        "result":row.get("result",""),"created_at":row.get("created_at",""),
        "first_land_day":traj["first_land_day"],"first_animal_day":traj["first_animal_day"],
        "peak_land":traj["peak_land"],"peak_animals":traj["peak_animals"],"peak_crops":traj["peak_crops"],
        "max_weed_ratio":traj["max_weed_ratio"],
        "money_d10":d(10,"money"),"money_d15":d(15,"money"),"money_d20":d(20,"money"),
        "money_d25":d(25,"money"),"money_d29":d(29,"money"),
        "strawberry_d15":d(15,"crop_STRAWBERRY"),"strawberry_d20":d(20,"crop_STRAWBERRY"),
        "animals_d15":d(15,"animal_total"),"animals_d20":d(20,"animal_total"),
        "land_d10":d(10,"land"),"land_d15":d(15,"land"),
        "actions":{k:int(v) for k,v in traj["actions"].items()},
    }


def aggregate(items):
    if not items: return {}
    metrics=["reward","opponent_reward","peak_land","peak_animals","peak_crops","max_weed_ratio",
             "money_d10","money_d15","money_d20","money_d25","money_d29","strawberry_d15","strawberry_d20",
             "animals_d15","animals_d20","land_d10","land_d15"]
    out={"games":len(items),"wins":sum(x["result"]=="win" for x in items),"losses":sum(x["result"]=="loss" for x in items)}
    for m in metrics:
        vals=[fnum(x.get(m)) for x in items]
        out[m+"_mean"]=statistics.mean(vals)
        out[m+"_median"]=statistics.median(vals)
        out[m+"_p10"]=percentile(vals,.1)
        out[m+"_p90"]=percentile(vals,.9)
    out["seat0_games"]=sum(x["seat"]==0 for x in items)
    out["seat1_games"]=sum(x["seat"]==1 for x in items)
    out["seat0_reward_mean"]=statistics.mean([x["reward"] for x in items if x["seat"]==0]) if out["seat0_games"] else 0
    out["seat1_reward_mean"]=statistics.mean([x["reward"] for x in items if x["seat"]==1]) if out["seat1_games"] else 0
    action=Counter()
    for x in items: action.update(x["actions"])
    out["actions_per_game"]={k:round(v/len(items),2) for k,v in action.most_common()}
    return out


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--corpus",type=Path,default=Path("replay_db"))
    p.add_argument("--leaderboard-dir",type=Path,default=Path("artifacts/leaderboard"))
    p.add_argument("--competition-csv",type=Path,default=Path("artifacts/competitions.csv"))
    p.add_argument("--submissions-csv",type=Path,default=Path("artifacts/submissions.csv"))
    p.add_argument("--output",type=Path,default=Path("artifacts/live_gap"))
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)

    comps=rows(a.competition_csv); subs=rows(a.submissions_csv)
    rank=int(fnum(pick_col(comps[0],"userRank"),0)) if comps else 0
    v19=[r for r in subs if "v19.0.0-live-rc1" in str(pick_col(r,"fileName","filename"))]
    v19_score=max([fnum(pick_col(r,"publicScore","score")) for r in v19] or [0])
    inferred=infer_team(a.leaderboard_dir,rank,v19_score)
    team=(inferred.get("chosen") or {}).get("team","")

    idx=rows(a.corpus/"index.csv")
    if team:
        ours=[r for r in idx if norm(str(r.get("team") or ""))==norm(team)]
    else:
        ours=[]
    resolved=[r for r in idx if r.get("reward") not in (None,"") and r.get("identity_source")!="unresolved"]
    # Freshest first for our team; strongest contemporaneous trajectories for comparison.
    ours=sorted(ours,key=lambda r:(str(r.get("created_at") or ""),fnum(r.get("reward"))),reverse=True)[:40]
    frontier=sorted(resolved,key=lambda r:fnum(r.get("reward")),reverse=True)[:40]

    def parse(items):
        out=[]
        for r in items:
            path=Path(str(r.get("source") or "")); ep=_load(path,str(r.get("episode_id") or ""))
            if ep is None: continue
            out.append(compact(r,_trajectory(ep,int(r.get("seat") or 0))))
        return out
    own=parse(ours); top=parse(frontier)

    own_agg=aggregate(own); top_agg=aggregate(top)
    win_agg=aggregate([x for x in own if x["result"]=="win"])
    loss_agg=aggregate([x for x in own if x["result"]=="loss"])

    gaps={}
    for key in ["reward_median","peak_land_median","peak_animals_median","peak_crops_median","max_weed_ratio_median",
                "money_d10_median","money_d15_median","money_d20_median","money_d25_median","money_d29_median",
                "strawberry_d15_median","strawberry_d20_median","animals_d15_median","animals_d20_median"]:
        if key in own_agg and key in top_agg:
            gaps[key]=top_agg[key]-own_agg[key]

    # Heuristic diagnosis is descriptive and explicitly tied to measured gaps.
    diagnoses=[]
    if own_agg and top_agg:
        if gaps.get("money_d10_median",0)>2000: diagnoses.append("early_capital_gap")
        if gaps.get("peak_animals_median",0)>=3: diagnoses.append("livestock_scale_gap")
        if gaps.get("strawberry_d20_median",0)>=8: diagnoses.append("premium_crop_throughput_gap")
        if own_agg.get("max_weed_ratio_median",0)>top_agg.get("max_weed_ratio_median",0)+.05: diagnoses.append("weed_service_gap")
        if gaps.get("money_d25_median",0)>10000: diagnoses.append("late_compounding_gap")
        if own_agg.get("seat0_reward_mean",0) and own_agg.get("seat1_reward_mean",0):
            lo=min(own_agg["seat0_reward_mean"],own_agg["seat1_reward_mean"]); hi=max(own_agg["seat0_reward_mean"],own_agg["seat1_reward_mean"])
            if hi>lo*1.25: diagnoses.append("seat_asymmetry")

    report={
        "current_rank":rank,"v19_live_score":v19_score,"team_inference":inferred,
        "our_replay_rows_found":len(ours),"our_replays_parsed":len(own),"frontier_parsed":len(top),
        "ours":own_agg,"ours_wins":win_agg,"ours_losses":loss_agg,"fresh_frontier":top_agg,
        "gaps_top_minus_ours":gaps,"diagnoses":diagnoses,
        "our_latest_games":own[:20],"frontier_examples":top[:10],
    }
    (a.output/"live_v19_gap.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))

if __name__=="__main__": main()
