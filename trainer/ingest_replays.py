"""Fast zero-copy indexer for harvested Kaggriculture replay JSON.

The harvester already stores each replay member as gzip-compressed JSON. This
indexer therefore does NOT create another copy of the corpus. It parses files in
parallel, deduplicates episodes, extracts replay/submission metadata and writes a
chronological index that points back to the harvested source file.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping


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
        out: list[float | None] = []
        for seat in (0, 1):
            try:
                reward = (steps[-1][seat] or {}).get("reward")
                out.append(float(reward) if reward is not None else None)
            except Exception:
                out.append(None)
        return out[0], out[1]
    return None, None


def _player_meta(episode: Mapping[str, Any], seat: int) -> Mapping[str, Any]:
    metadata = episode.get("metadata") if isinstance(episode.get("metadata"), Mapping) else {}
    info = episode.get("info") if isinstance(episode.get("info"), Mapping) else {}
    candidates = [
        episode.get("agents"), episode.get("players"),
        metadata.get("agents"), metadata.get("players"), info.get("agents"), info.get("players"),
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
    family = submission or team or f"unknown:{Path(source).parent.name}:{Path(source).name}"
    return submission, team or family


def _parse_file(raw_path: str) -> list[Dict[str, Any]]:
    path = Path(raw_path)
    try:
        if path.suffix.lower() == ".gz":
            with gzip.open(path, "rb") as handle:
                payload = handle.read()
        elif path.suffix.lower() == ".json":
            payload = path.read_bytes()
        else:
            return []
        data = json.loads(payload.decode("utf-8-sig"))
    except Exception:
        return []

    fallback_hash = hashlib.sha256(payload).hexdigest()
    parsed: list[Dict[str, Any]] = []
    for ordinal, episode in enumerate(_walk(data)):
        eid = _episode_id(episode)
        digest = fallback_hash if ordinal == 0 else hashlib.sha256(
            json.dumps(episode, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        r0, r1 = _final_rewards(episode)
        base = {
            "episode_id": eid or digest[:20],
            "dedupe_key": f"id:{eid}" if eid else f"sha:{digest}",
            "sha256": digest,
            "source": raw_path,
            "created_at": _created_at(episode),
            "steps": len(episode.get("steps") or []),
        }
        for seat, own, opp in ((0, r0, r1), (1, r1, r0)):
            result = ""
            if own is not None and opp is not None:
                result = "win" if own > opp else "loss" if own < opp else "tie"
            submission_id, team = _identity(episode, seat, raw_path)
            parsed.append({
                **base,
                "seat": seat,
                "submission_id": submission_id,
                "team": team,
                "reward": own,
                "opponent_reward": opp,
                "result": result,
            })
    return parsed


def ingest(input_dir: Path, output_dir: Path, workers: int | None = None) -> None:
    paths = sorted(
        p for p in input_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in {".gz", ".json"} and p.name != "harvest_summary.json"
    )
    if not paths:
        raise RuntimeError(f"No replay JSON files found under {input_dir}")

    worker_count = workers or max(2, min(8, os.cpu_count() or 2))
    print(json.dumps({"files_to_index": len(paths), "workers": worker_count}))

    raw_rows: list[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=worker_count) as pool:
        futures = {pool.submit(_parse_file, str(path)): path for path in paths}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            rows = future.result()
            raw_rows.extend(rows)
            if completed % 250 == 0 or completed == len(paths):
                print(json.dumps({"indexed_files": completed, "trajectory_rows_seen": len(raw_rows)}), flush=True)

    # Deduplicate by episode, preserving both seat rows from the first encountered copy.
    by_episode: dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        by_episode[str(row["dedupe_key"])].append(row)

    rows: list[Dict[str, Any]] = []
    for episode_rows in by_episode.values():
        # A single episode contributes at most one row per seat.
        seats: set[int] = set()
        for row in episode_rows:
            seat = int(row["seat"])
            if seat in seats:
                continue
            seats.add(seat)
            row.pop("dedupe_key", None)
            row["window"] = ""
            row["recency_rank"] = ""
            rows.append(row)

    grouped: dict[str, list[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        family = row["submission_id"] or row["team"] or f"unknown:{Path(str(row['source'])).name}"
        grouped[f"{family}:seat{row['seat']}"].append(row)

    for family_rows in grouped.values():
        family_rows.sort(
            key=lambda r: (_parse_time(str(r["created_at"])), str(r["episode_id"])),
            reverse=True,
        )
        for rank, row in enumerate(family_rows):
            row["recency_rank"] = rank
            row["window"] = (
                "outer" if rank < 6 else
                "option_validation" if rank < 9 else
                "route_validation" if rank < 12 else
                "fit" if rank < 24 else
                "archive"
            )

    output_dir.mkdir(parents=True, exist_ok=True)
    fields = [
        "episode_id", "sha256", "source", "created_at", "seat", "submission_id", "team",
        "reward", "opponent_reward", "result", "steps", "window", "recency_rank",
    ]
    with (output_dir / "index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "unique_episodes": len(by_episode),
        "trajectory_rows": len(rows),
        "families": len(grouped),
        "fit_rows": sum(row["window"] == "fit" for row in rows),
        "outer_rows": sum(row["window"] == "outer" for row in rows),
        "source_files_indexed": len(paths),
        "zero_copy": True,
        "workers": worker_count,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("replay_db"))
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    ingest(args.input, args.output, args.workers)
