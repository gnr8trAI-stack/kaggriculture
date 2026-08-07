"""Space-efficient Kaggriculture replay harvester using Kaggle CLI.

Authentication is read from KAGGLE_API_TOKEN. Public episode datasets are
processed one at a time. JSON members are streamed directly from ZIP archives
into gzip-compressed files and the downloaded archive/staging directory is
removed immediately, keeping GitHub-hosted runner disk usage bounded.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path


def _run(args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(args), flush=True)
    result = subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=check,
    )
    # Avoid flooding the Actions diagnostic log with very large CLI output.
    if result.stdout:
        print(result.stdout[-12000:], flush=True)
    return result


def _dataset_refs() -> list[str]:
    result = _run(["kaggle", "datasets", "list", "-s", "kaggriculture-episodes", "--csv"])
    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    refs: list[str] = []
    for row in rows:
        ref = (row.get("ref") or row.get("Ref") or "").strip()
        if ref and "kaggriculture-episodes" in ref.lower():
            refs.append(ref)
    # Names are date-suffixed, so descending lexical order normally processes
    # the newest public population first while still scanning all references.
    return sorted(set(refs), reverse=True)


def _stream_zip_json(zip_path: Path, destination: Path, prefix: str) -> tuple[int, int]:
    destination.mkdir(parents=True, exist_ok=True)
    json_members = 0
    bytes_written = 0
    with zipfile.ZipFile(zip_path) as archive:
        for index, info in enumerate(archive.infolist()):
            if info.is_dir():
                continue
            lower = info.filename.lower()
            if not lower.endswith(".json"):
                continue
            json_members += 1
            safe_name = f"{prefix}-{index:06d}.json.gz"
            out = destination / safe_name
            with archive.open(info, "r") as src, gzip.open(out, "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            bytes_written += out.stat().st_size
    return json_members, bytes_written


def _process_download_dir(download_dir: Path, destination: Path, prefix: str) -> tuple[int, int]:
    json_files = 0
    bytes_written = 0
    serial = 0
    for path in sorted(download_dir.rglob("*")):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if lower.endswith(".zip"):
            count, written = _stream_zip_json(path, destination, f"{prefix}-z{serial:03d}")
            serial += 1
            json_files += count
            bytes_written += written
            path.unlink(missing_ok=True)
        elif lower.endswith(".json"):
            out = destination / f"{prefix}-j{serial:06d}.json.gz"
            serial += 1
            with path.open("rb") as src, gzip.open(out, "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            json_files += 1
            bytes_written += out.stat().st_size
            path.unlink(missing_ok=True)
    return json_files, bytes_written


def harvest(output: Path, max_datasets: int | None = None) -> dict:
    if not os.environ.get("KAGGLE_API_TOKEN"):
        raise RuntimeError("KAGGLE_API_TOKEN is not set")

    output.mkdir(parents=True, exist_ok=True)
    compact_dir = output / "replays_gz"
    compact_dir.mkdir(exist_ok=True)
    staging_root = output / "_staging"
    staging_root.mkdir(exist_ok=True)

    refs = _dataset_refs()
    if max_datasets is not None:
        refs = refs[:max_datasets]
    if not refs:
        raise RuntimeError("No public kaggriculture-episodes datasets were discovered")

    downloaded: list[str] = []
    failed: list[dict[str, str | int]] = []
    dataset_stats: list[dict[str, str | int]] = []
    total_json = 0
    total_compressed_bytes = 0

    for ordinal, ref in enumerate(refs):
        print(f"\n=== dataset {ordinal + 1}/{len(refs)}: {ref} ===", flush=True)
        safe = ref.replace("/", "__").replace(" ", "_")
        stage = staging_root / safe
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir(parents=True, exist_ok=True)

        result = _run(
            ["kaggle", "datasets", "download", "-d", ref, "-p", str(stage), "--force"],
            check=False,
        )
        if result.returncode != 0:
            failed.append({"ref": ref, "returncode": result.returncode})
            shutil.rmtree(stage, ignore_errors=True)
            continue

        try:
            count, written = _process_download_dir(stage, compact_dir, f"d{ordinal:04d}")
        finally:
            shutil.rmtree(stage, ignore_errors=True)

        downloaded.append(ref)
        total_json += count
        total_compressed_bytes += written
        dataset_stats.append({
            "ref": ref,
            "json_files": count,
            "compressed_bytes": written,
        })
        print(
            json.dumps(
                {
                    "dataset": ref,
                    "json_files": count,
                    "compressed_mb": round(written / 1024 / 1024, 2),
                    "total_json": total_json,
                    "total_compressed_mb": round(total_compressed_bytes / 1024 / 1024, 2),
                }
            ),
            flush=True,
        )
        shutil.disk_usage(output)  # touch filesystem before next download

    shutil.rmtree(staging_root, ignore_errors=True)

    summary = {
        "dataset_refs_discovered": refs,
        "datasets_downloaded": downloaded,
        "datasets_failed": failed,
        "dataset_stats": dataset_stats,
        "json_files": total_json,
        "compressed_bytes": total_compressed_bytes,
    }
    (output / "harvest_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)

    if total_json == 0:
        raise RuntimeError("Harvest completed but no replay JSON files were retained")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("raw_kaggle_replays"))
    parser.add_argument("--max-datasets", type=int)
    args = parser.parse_args()
    harvest(args.output, args.max_datasets)
