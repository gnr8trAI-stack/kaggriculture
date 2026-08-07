"""Ingest Kaggriculture replay JSON into a deduplicated chronological corpus."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Tuple


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _hash_episode(episode: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(episode)).hexdigest()


def _looks_like_episode(value: Any) -> bool:
    return isinstance(value, Mapping) and isinstance(value.get("steps"), list) and bool(value.get("steps"))


def _walk(value: Any) -> Iterator[Mapping[str, Any]]:
    if _looks_like_episode(value):
        yield value
        return
    if isinstance(value, Mapping):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _load_file(path: Path) -> Iterator[Tuple[Mapping[str, Any], str]]:
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception:
            return
        for episode in _walk(data):
            yield episode, str(path)
    elif path.suffix.lower() == ".gz":
        try:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return
        for episode in _walk(data):
            yield episode, str(path)


def _episode_id(episode: Mapping[str, Any]) -> str:
    for container in (episode, episode.get("metadata") or {}, episode.get("info") or {}):
        if isinstance(container, Mapping):
            for key in ("episodeId", "episode_id", "id"):
                value = container.get(key)
                if value not in (None, ""):
                    return str(value)
    return ""


def _created_at(episode: Mapping[str, Any]) -> str:
    for container in (episode, episode.get("metadata") or {}, episode.get("info") or {}):
        if isinstance(container, Mapping):
            for key in ("createdAt", "created_at", "startedAt", "started_at"):
                value = container.get(key)
                if value:
                    return str(value)
    return ""


def _parse_time(value: str) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _final_rewards(episode: Mapping[str, Any]) -> tuple[float | None, float | None]:
    rewards = episode.get("rewards")
    if isinstance(rewards, list) and len(rewards) >= 2:
        try:
            return float(rewards[0]), float(rewards[1])
        except Exception:
            pass
    steps = episode.get("steps") or []
    if steps and isinstance(steps[-1], list) and len(steps[-1]) >= 2:
        out = []
        for seat in (0, 1):
            try:
                out.append(float((steps[-1][seat] or {}).get("reward") or 0))
            except Exception:
                out.append(None)
        return out[0], out[1]
    return None, None


def _player_meta(episode: Mapping[str, Any], seat: int) -> Mapping[str, Any]:
    candidates = [
        episode.get("agents"),
        episode.get("players"),
        (episode.get("metadata") or {}).get("agents") if isinstance(episode.get("metadata"), Mapping) else None,
        (episode.get("metadata") or {}).get("players") if isinstance(episode.get("metadata"), Mapping) else None,
        (episode.get("info") or {}).get("agents") if isinstance(episode.get("info"), Mapping) else None,
    ]
    for candidate in candidates:
        if isinstance(candidate, list) and seat < len(candidate) and isinstance(candidate[seat], Mapping):
            return candidate[seat]
    return {}


def _first(meta: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = meta.get(key)
        if value not in (None, ""):
            if isinstance(value, Mapping):
                for nested in ("id", "name", "submissionId", "submission_id"):
                    if value.get(nested) not in (None, ""):
                        return str(value[nested])
            return str(value)
    return ""


def _identity(episode: Mapping[str, Any], seat: int, source: str) -> tuple[str, str]:
    meta = _player_meta(episode, seat)
    submission = _first(meta, "submissionId", "submission_id", "submission")
    team = _first(meta, "teamName", "team_name", "team", "name")
    if not submission:
        # Some exports place submission ids in episode-level arrays.
        for container in (episode, episode.get("metadata") or {}, episode.get("info") or {}):
            if not isinstance(container, Mapping):
                continue
            for key in ("submissionIds", "submission_ids"):
                values = container.get(key)
                if isinstance(values, list) and seat < len(values) and values[seat] not in (None, ""):
                    submission = str(values[seat])
                    break
            if submission:
                break
    # Keep unknown sources separate instead of collapsing the whole population.
    family = submission or team or f"unknown:{Path(source).name}"
    return submission, team or family


def ingest(input_dir: Path, output_dir: Path) -> None:
    episodes_dir = output_dir / "episodes"
    episodes_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    rows: list[Dict[str, Any]] = []

    for path in sorted(p for p in input_dir.rglob("*") if p.is_file()):
        for episode, source in _load_file(path):
            digest = _hash_episode(episode)
            eid = _episode_id(episode)
            key = f"id:{eid}" if eid else f"sha:{digest}"
            if key in seen:
                continue
            seen.add(key)
            safe_id = eid or digest[:20]
            with gzip.open(episodes_dir / f"{safe_id}.json.gz", "wt", encoding="utf-8") as handle:
                json.dump(episode, handle, separators=(",", ":"))
            r0, r1 = _final_rewards(episode)
            for seat, own, opp in ((0, r0, r1), (1, r1, r0)):
                result = ""
                if own is not None and opp is not None:
                    result = "win" if own > opp else "loss" if own < opp else "tie"
                submission_id, team = _identity(episode, seat, source)
                rows.append({
                    "episode_id": safe_id,
                    "sha256": digest,
                    "source": source,
                    "created_at": _created_at(episode),
                    "seat": seat,
                    "submission_id": submission_id,
                    "team": team,
                    "reward": own,
                    "opponent_reward": opp,
                    "result": result,
                    "steps": len(episode.get("steps") or []),
                    "window": "",
                    "recency_rank": "",
                })

    grouped: dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        family = row["submission_id"] or row["team"] or f"unknown:{Path(str(row['source'])).name}"
        grouped[f"{family}:seat{row['seat']}"].append(row)
    for family in grouped.values():
        family.sort(key=lambda r: (_parse_time(str(r["created_at"])), str(r["episode_id"])), reverse=True)
        for rank, row in enumerate(family):
            row["recency_rank"] = rank
            row["window"] = (
                "outer" if rank < 6 else
                "option_validation" if rank < 9 else
                "route_validation" if rank < 12 else
                "fit" if rank < 24 else
                "archive"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    fields = ["episode_id", "sha256", "source", "created_at", "seat", "submission_id", "team", "reward", "opponent_reward", "result", "steps", "window", "recency_rank"]
    with (output_dir / "index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "unique_episodes": len(seen),
        "trajectory_rows": len(rows),
        "families": len(grouped),
        "fit_rows": sum(row["window"] == "fit" for row in rows),
        "outer_rows": sum(row["window"] == "outer" for row in rows),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("replay_db"))
    args = parser.parse_args()
    ingest(args.input, args.output)
