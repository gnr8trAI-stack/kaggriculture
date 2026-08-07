"""Download the available Kaggriculture replay/episode datasets using Kaggle CLI.

Authentication is read from KAGGLE_API_TOKEN. The script deliberately downloads
raw public datasets only; learning happens in the separate ingestion/build steps.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args))
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check)


def _dataset_refs() -> list[str]:
    # CSV output is intentionally parsed by header name because Kaggle CLI column
    # order has changed across releases.
    result = _run(["kaggle", "datasets", "list", "-s", "kaggriculture-episodes", "--csv"])
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    refs: list[str] = []
    for row in rows:
        ref = (row.get("ref") or row.get("Ref") or "").strip()
        if ref and "kaggriculture-episodes" in ref.lower():
            refs.append(ref)
    return sorted(set(refs))


def _extract_all(root: Path) -> None:
    # Recursively extract ZIPs because Kaggle dataset and competition downloads
    # are commonly nested archives.
    pending = list(root.rglob("*.zip"))
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        target = path.with_suffix("")
        target.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(path) as archive:
                archive.extractall(target)
        except zipfile.BadZipFile:
            continue
        pending.extend(target.rglob("*.zip"))


def harvest(output: Path, max_datasets: int | None = None) -> dict:
    if not os.environ.get("KAGGLE_API_TOKEN"):
        raise RuntimeError("KAGGLE_API_TOKEN is not set")
    output.mkdir(parents=True, exist_ok=True)

    # Competition package may itself contain replay snapshots or manifests.
    competition_dir = output / "competition"
    competition_dir.mkdir(exist_ok=True)
    competition = _run([
        "kaggle", "competitions", "download", "kaggriculture",
        "-p", str(competition_dir), "--force",
    ], check=False)
    print(competition.stdout)

    refs = _dataset_refs()
    if max_datasets is not None:
        refs = refs[-max_datasets:]
    if not refs:
        raise RuntimeError("No public kaggriculture-episodes datasets were discovered")

    downloaded = []
    datasets_dir = output / "datasets"
    datasets_dir.mkdir(exist_ok=True)
    for ref in refs:
        safe = ref.replace("/", "__")
        dest = datasets_dir / safe
        dest.mkdir(parents=True, exist_ok=True)
        result = _run(["kaggle", "datasets", "download", "-d", ref, "-p", str(dest), "--force"], check=False)
        print(result.stdout)
        if result.returncode == 0:
            downloaded.append(ref)

    _extract_all(output)
    replay_like = [
        p for p in output.rglob("*.json")
        if "replay" in p.name.lower() or "episode" in p.name.lower() or p.stat().st_size > 1024
    ]
    summary = {
        "dataset_refs_discovered": refs,
        "datasets_downloaded": downloaded,
        "json_files": len(list(output.rglob("*.json"))),
        "replay_like_json_files": len(replay_like),
    }
    (output / "harvest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not replay_like:
        raise RuntimeError("Harvest completed but no replay-like JSON files were found")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("raw_kaggle_replays"))
    parser.add_argument("--max-datasets", type=int)
    args = parser.parse_args()
    harvest(args.output, args.max_datasets)
