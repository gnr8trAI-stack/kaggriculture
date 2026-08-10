#!/usr/bin/env python3
"""Live Kaggriculture telemetry/control-plane collector.

Fetches authenticated rank/submission state, direct live episode metadata and a
small replay sample. Produces machine-readable state that can drive build/test/
submit automation without relying on chat memory.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from kaggle.api.kaggle_api_extended import KaggleApi

COMPETITION = os.getenv("KAGGLE_COMPETITION", "kaggriculture")
TEAM = os.getenv("KAGGLE_TEAM_NAME", "Gnr8tr")
DAILY_LIMIT = int(os.getenv("KAGGLE_DAILY_LIMIT", "5"))
RESERVE_SLOTS = int(os.getenv("KAGGLE_RESERVE_SLOTS", "1"))
EPISODE_DAYS = int(os.getenv("KAGGLE_EPISODE_DAYS", "2"))
REPLAY_WINS = int(os.getenv("KAGGLE_REPLAY_WINS", "5"))
REPLAY_LOSSES = int(os.getenv("KAGGLE_REPLAY_LOSSES", "5"))
OUT = Path(os.getenv("KAGGLE_CONTROL_OUT", "artifacts/control_plane"))
PREVIOUS = os.getenv("KAGGLE_PREVIOUS_STATE", "")


def sh_csv(args: list[str]) -> list[dict[str, str]]:
    text = subprocess.check_output(args, text=True)
    return list(csv.DictReader(text.splitlines()))


def fnum(x: Any) -> float | None:
    try:
        if x in (None, ""): return None
        return float(x)
    except Exception:
        return None


def inum(x: Any) -> int | None:
    try:
        if x in (None, ""): return None
        return int(float(x))
    except Exception:
        return None


def parse_cli_dt(s: str) -> datetime | None:
    if not s: return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try: return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError: pass
    return None


def objdict(x: Any) -> dict[str, Any]:
    if isinstance(x, dict): return x
    if hasattr(x, "to_dict"):
        try: return x.to_dict()
        except Exception: pass
    if hasattr(x, "__dict__"):
        return {k: v for k, v in x.__dict__.items() if not k.startswith("_")}
    return {"repr": repr(x)}


def pick(d: dict[str, Any], *names: str, default=None):
    norm = lambda s: "".join(c for c in str(s).lower() if c.isalnum())
    wanted = {norm(n) for n in names}
    for k, v in d.items():
        if norm(k) in wanted: return v
    return default


def action_key(action: Any) -> str:
    if not isinstance(action, list) or not action: return "INVALID"
    op = str(action[0])
    if op in {"PLANT", "PICKUP", "PLACE"} and len(action) > 1:
        return f"{op}:{action[1]}"
    if op in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL"} and len(action) > 1:
        return f"{op}:{action[1]}"
    return op


def replay_signature(path: Path, team: str) -> dict[str, Any]:
    d = json.loads(path.read_text(encoding="utf-8"))
    names = d.get("info", {}).get("TeamNames") or [a.get("Name") for a in d.get("info", {}).get("Agents", [])]
    if team not in names:
        return {"episode_id": d.get("info", {}).get("EpisodeId"), "error": f"team {team!r} not found", "team_names": names}
    idx = names.index(team)
    opp_idx = 1 - idx
    ours = Counter(); opp = Counter(); ours_market = Counter(); opp_market = Counter()
    daily: dict[int, dict[str, Any]] = {}
    first_land2 = first_land3 = None
    peak = {"hands": 0, "land": 0, "crops": 0, "strawberry": 0, "animals": 0, "cows": 0, "sheep": 0, "money": 0.0}

    def consume(counter: Counter, market_counter: Counter, a: Any):
        if not isinstance(a, dict): return
        farmer = a.get("farmer")
        counter[action_key(farmer)] += 1
        for h in a.get("hands") or []: counter[action_key(h)] += 1
        for m in a.get("market") or []:
            k = action_key(m); counter[k] += 1; market_counter[k] += 1

    for turn, step in enumerate(d.get("steps") or []):
        if len(step) < 2: continue
        consume(ours, ours_market, step[idx].get("action"))
        consume(opp, opp_market, step[opp_idx].get("action"))
        obs = step[idx].get("observation") or {}
        farms = obs.get("farms") or []
        if idx >= len(farms): continue
        farm = farms[idx] or {}
        day = int(obs.get("day", turn // 24))
        land = len(farm.get("unlocked_quadrants") or [])
        hands = len(farm.get("hands") or [])
        money = float(farm.get("money") or 0)
        crops = strawberry = animals = cows = sheep = 0
        for row in farm.get("tiles") or []:
            for tile in row or []:
                if not isinstance(tile, dict): continue
                kind = tile.get("kind")
                if kind == "PLANT":
                    crops += 1
                    if tile.get("crop") == "STRAWBERRY": strawberry += 1
                elif kind == "PASTURE" and tile.get("animal"):
                    animals += 1
                    if tile.get("animal") == "COW": cows += 1
                    if tile.get("animal") == "SHEEP": sheep += 1
        peak["hands"] = max(peak["hands"], hands)
        peak["land"] = max(peak["land"], land)
        peak["crops"] = max(peak["crops"], crops)
        peak["strawberry"] = max(peak["strawberry"], strawberry)
        peak["animals"] = max(peak["animals"], animals)
        peak["cows"] = max(peak["cows"], cows)
        peak["sheep"] = max(peak["sheep"], sheep)
        peak["money"] = max(peak["money"], money)
        if land >= 2 and first_land2 is None: first_land2 = day
        if land >= 3 and first_land3 is None: first_land3 = day
        daily[day] = {"turn": turn, "money": money, "hands": hands, "land": land, "crops": crops,
                      "strawberry": strawberry, "animals": animals, "cows": cows, "sheep": sheep}

    rewards = d.get("rewards") or [None, None]
    return {
        "episode_id": d.get("info", {}).get("EpisodeId"), "seed": d.get("info", {}).get("seed"),
        "our_index": idx, "opponent": names[opp_idx],
        "our_reward": rewards[idx] if idx < len(rewards) else None,
        "opponent_reward": rewards[opp_idx] if opp_idx < len(rewards) else None,
        "first_land2_day": first_land2, "first_land3_day": first_land3, "peak": peak,
        "our_actions": dict(ours.most_common()), "opponent_actions": dict(opp.most_common()),
        "our_market_actions": dict(ours_market.most_common()), "opponent_market_actions": dict(opp_market.most_common()),
        "daily": [daily[k] | {"day": k} for k in sorted(daily)],
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    replay_dir = OUT / "replays"; replay_dir.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    comp_rows = sh_csv(["kaggle", "competitions", "list", "--group", "entered", "-s", COMPETITION, "--csv"])
    comp = next((r for r in comp_rows if COMPETITION in (r.get("ref") or "")), comp_rows[0] if comp_rows else {})
    submissions = sh_csv(["kaggle", "competitions", "submissions", COMPETITION, "-v", "-q"])
    for r in submissions:
        r["submission_id"] = inum(r.get("ref")); r["public_score"] = fnum(r.get("publicScore")); r["submitted_at_utc"] = r.get("date")
    parsed = [(r, parse_cli_dt(r.get("date", ""))) for r in submissions]
    today_subs = [r for r, dt in parsed if dt and dt.date().isoformat() == today]
    recent_cut = now - timedelta(days=EPISODE_DAYS)
    recent_subs = [r for r, dt in parsed if dt and dt >= recent_cut]
    latest = submissions[0] if submissions else None
    scored = [r for r in submissions if r.get("public_score") is not None]
    best = max(scored, key=lambda r: r["public_score"]) if scored else None

    api = KaggleApi(); api.authenticate()
    episode_rows: list[dict[str, Any]] = []
    seen_ep = set()
    for sub in recent_subs:
        sid = sub.get("submission_id")
        if not sid: continue
        try: eps = api.competition_list_episodes(sid) or []
        except Exception as e:
            sub["episode_error"] = repr(e); continue
        for ep in eps:
            d = objdict(ep); eid = inum(pick(d, "id", "episodeId", "episode_id"))
            if not eid or (sid, eid) in seen_ep: continue
            seen_ep.add((sid, eid))
            agents = [objdict(a) for a in (pick(d, "agents", default=[]) or [])]
            ours = next((a for a in agents if inum(pick(a, "submissionId", "submission_id")) == sid), None)
            opp = next((a for a in agents if ours is None or a is not ours), None)
            orw = fnum(pick(ours or {}, "reward")); prw = fnum(pick(opp or {}, "reward"))
            typ = pick(d, "type")
            result = "unknown"
            if typ == "EPISODE_TYPE_PUBLIC" and orw is not None and prw is not None:
                result = "win" if orw > prw else "loss" if orw < prw else "tie"
            episode_rows.append({
                "submission_id": sid, "fileName": sub.get("fileName"), "episode_id": eid,
                "create_time": str(pick(d, "createTime", "create_time", default="") or ""),
                "end_time": str(pick(d, "endTime", "end_time", default="") or ""), "type": typ,
                "result": result, "our_reward": orw, "opponent_reward": prw,
                "opponent_team": pick(opp or {}, "teamName", "team_name"),
                "opponent_submission_id": inum(pick(opp or {}, "submissionId", "submission_id")),
            })

    episode_rows.sort(key=lambda r: r.get("create_time") or "", reverse=True)
    public_eps = [r for r in episode_rows if r["result"] in {"win", "loss", "tie"}]
    wins = [r for r in public_eps if r["result"] == "win"]
    losses = [r for r in public_eps if r["result"] == "loss"]

    # Per-submission live stats.
    stats = {}
    for sub in recent_subs:
        sid = sub.get("submission_id"); games = [r for r in public_eps if r["submission_id"] == sid]
        w = sum(r["result"] == "win" for r in games); l = sum(r["result"] == "loss" for r in games); t = sum(r["result"] == "tie" for r in games)
        margins = [(r["our_reward"] or 0) - (r["opponent_reward"] or 0) for r in games]
        stats[str(sid)] = {
            "submission_id": sid, "fileName": sub.get("fileName"), "submitted_at_utc": sub.get("date"),
            "public_score": sub.get("public_score"), "games": len(games), "wins": w, "losses": l, "ties": t,
            "win_rate": (w / len(games)) if games else None,
            "mean_reward": statistics.fmean([r["our_reward"] for r in games if r["our_reward"] is not None]) if games else None,
            "mean_opponent_reward": statistics.fmean([r["opponent_reward"] for r in games if r["opponent_reward"] is not None]) if games else None,
            "mean_margin": statistics.fmean(margins) if margins else None,
        }

    # Direct replay sample: newest wins and losses, prioritising latest submissions.
    selected = []
    for group, n in ((wins, REPLAY_WINS), (losses, REPLAY_LOSSES)):
        selected.extend(group[:n])
    signatures = []
    for r in selected:
        eid = r["episode_id"]
        path = replay_dir / f"episode-{eid}-replay.json"
        try:
            if not path.exists(): api.competition_episode_replay(eid, path=str(replay_dir), quiet=True)
            # Kaggle names the downloaded file episode-<id>-replay.json.
            actual = path if path.exists() else next(replay_dir.glob(f"*{eid}*"))
            sig = replay_signature(actual, TEAM); sig["result"] = r["result"]; sig["submission_id"] = r["submission_id"]
            signatures.append(sig)
        except Exception as e:
            signatures.append({"episode_id": eid, "submission_id": r["submission_id"], "result": r["result"], "error": repr(e)})

    prev = {}
    if PREVIOUS and Path(PREVIOUS).exists():
        try: prev = json.loads(Path(PREVIOUS).read_text())
        except Exception: prev = {}
    rank = inum(comp.get("userRank")); teams = inum(comp.get("teamCount"))
    prev_rank = ((prev.get("competition") or {}).get("rank")) if prev else None
    rank_delta = (rank - prev_rank) if rank is not None and isinstance(prev_rank, int) else None
    used = len(today_subs); remaining = max(0, DAILY_LIMIT - used)
    latest_sid = latest.get("submission_id") if latest else None
    latest_stats = stats.get(str(latest_sid), {})
    min_games_before_rotate = int(os.getenv("KAGGLE_MIN_GAMES_BEFORE_ROTATE", "10"))
    if remaining <= 0:
        next_action = "quota_exhausted_observe_only"
    elif remaining <= RESERVE_SLOTS:
        next_action = "hold_reserved_slot_or_restore_champion"
    elif latest_stats.get("games", 0) < min_games_before_rotate:
        next_action = "observe_current_agent_until_min_games"
    else:
        next_action = "eligible_to_test_one_staged_challenger"

    state = {
        "schema_version": 1, "generated_at_utc": now.isoformat(),
        "competition": {"ref": comp.get("ref"), "rank": rank, "team_count": teams, "rank_delta_since_previous": rank_delta,
                        "deadline": comp.get("deadline"), "entered": comp.get("userHasEntered")},
        "quota": {"date_utc": today, "daily_limit": DAILY_LIMIT, "used": used, "remaining": remaining, "reserved_slots": RESERVE_SLOTS},
        "latest_submission": latest, "best_historical_submission": best,
        "today_submissions": today_subs, "recent_submission_stats": stats,
        "episodes": {"recent_public_games": len(public_eps), "wins": len(wins), "losses": len(losses),
                     "ties": sum(r["result"] == "tie" for r in public_eps), "latest": episode_rows[:30]},
        "replay_signatures": signatures,
        "automation": {"min_games_before_rotate": min_games_before_rotate, "next_action": next_action,
                       "auto_submit_allowed_by_quota": remaining > RESERVE_SLOTS,
                       "rule": "one challenger at a time; keep reserve slot unless explicitly overridden"},
    }
    (OUT / "latest.json").write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    (OUT / "replay_signatures.json").write_text(json.dumps(signatures, indent=2, default=str), encoding="utf-8")
    with (OUT / "submissions.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["ref", "fileName", "date", "description", "status", "publicScore", "privateScore"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(submissions)
    with (OUT / "episodes.csv").open("w", newline="", encoding="utf-8") as f:
        cols = ["submission_id", "fileName", "episode_id", "create_time", "end_time", "type", "result", "our_reward", "opponent_reward", "opponent_team", "opponent_submission_id"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(episode_rows)
    md = [
        f"# Kaggriculture live state — {now.isoformat()}", "",
        f"- Rank: **{rank} / {teams}**" + (f" (delta {rank_delta:+d})" if rank_delta is not None else ""),
        f"- Submission quota UTC {today}: **{used}/{DAILY_LIMIT} used, {remaining} remaining**; reserve {RESERVE_SLOTS}",
        f"- Latest: **{latest.get('fileName') if latest else None}** score {latest.get('public_score') if latest else None}",
        f"- Best historical: **{best.get('fileName') if best else None}** score {best.get('public_score') if best else None}",
        f"- Recent public episodes: {len(public_eps)} = {len(wins)}W/{len(losses)}L/{sum(r['result']=='tie' for r in public_eps)}T",
        f"- Automation next action: **{next_action}**", "",
    ]
    (OUT / "SUMMARY.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
