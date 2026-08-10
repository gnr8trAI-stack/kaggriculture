#!/usr/bin/env python3
"""
Download KAggriculture competition replay corpus from Kaggle.
Requires kaggle API credentials configured at ~/.kaggle/kaggle.json
"""

import os
import json
import zipfile
from pathlib import Path
from kaggle.api.kaggle_api_extended import KaggleApi

def download_replay_corpus(output_dir: str = "data/replays"):
    """
    Download the complete replay corpus from the KAggriculture Kaggle competition.
    
    Args:
        output_dir: Directory to store the downloaded replays
    """
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print("Initializing Kaggle API...")
    api = KaggleApi()
    api.authenticate()
    
    print("Downloading KAggriculture competition data...")
    competition_name = "kaggriculture"
    
    # Download all files from the competition
    api.competition_download_files(competition_name, path=output_dir)
    
    print(f"✓ Downloaded to {output_dir}")
    
    # Extract zip files if present
    for zip_file in Path(output_dir).glob("*.zip"):
        print(f"Extracting {zip_file.name}...")
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(output_dir)
        zip_file.unlink()  # Remove zip after extraction
    
    # List downloaded files
    print("\nDownloaded files:")
    for file in Path(output_dir).iterdir():
        size_mb = file.stat().st_size / (1024 * 1024)
        print(f"  - {file.name} ({size_mb:.2f} MB)")
    
    print("\n✓ Replay corpus download complete!")
    return output_dir

if __name__ == "__main__":
    download_replay_corpus()
