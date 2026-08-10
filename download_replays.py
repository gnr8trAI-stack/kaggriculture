#!/usr/bin/env python3
"""
Download KAggriculture competition replay corpus from Kaggle.
Requires kaggle API credentials configured at ~/.kaggle/kaggle.json
"""

import os
import json
import zipfile
import subprocess
from pathlib import Path
from typing import List

def download_replay_corpus(output_dir: str = "data/replays") -> str:
    """
    Download the complete replay corpus from the KAggriculture Kaggle competition.
    
    Args:
        output_dir: Directory to store the downloaded replays
    
    Returns:
        Path to output directory
    """
    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print("Downloading KAggriculture competition data from Kaggle...")
    print(f"Output directory: {output_dir}")
    
    try:
        # Download competition data using kaggle CLI
        cmd = f"kaggle competitions download -c kaggriculture -p {output_dir} --quiet"
        print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)
        
        print("✓ Download initiated")
        
        # Extract zip files if present
        zip_files = list(Path(output_dir).glob("*.zip"))
        if zip_files:
            print(f"\nExtracting {len(zip_files)} archive(s)...")
            for zip_file in zip_files:
                print(f"  - Extracting {zip_file.name}...")
                try:
                    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                        zip_ref.extractall(output_dir)
                    zip_file.unlink()
                    print(f"    ✓ Extracted")
                except Exception as e:
                    print(f"    ⚠ Error: {e}")
        
        # List downloaded files
        print("\n✓ Files in replay directory:")
        json_files = list(Path(output_dir).glob("**/*.json"))
        for json_file in json_files[:20]:  # Show first 20
            size_kb = json_file.stat().st_size / 1024
            print(f"  - {json_file.name} ({size_kb:.1f} KB)")
        
        if len(json_files) > 20:
            print(f"  ... and {len(json_files) - 20} more files")
        
        print(f"\n✓ Total JSON files: {len(json_files)}")
        print(f"✓ Replay corpus download complete!")
        
        return output_dir
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error running kaggle command: {e}")
        print("\nMake sure you have:")
        print("  1. Kaggle CLI installed: pip install kaggle")
        print("  2. Credentials configured at ~/.kaggle/kaggle.json")
        print("  3. Accepted competition rules on Kaggle website")
        return None
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return None


def list_replays(replay_dir: str = "data/replays") -> List[Path]:
    """List all replay files."""
    replay_path = Path(replay_dir)
    if not replay_path.exists():
        print(f"Directory not found: {replay_dir}")
        return []
    
    replays = list(replay_path.glob("**/*.json"))
    return replays


if __name__ == "__main__":
    result = download_replay_corpus()
    if result:
        replays = list_replays(result)
        print(f"\nFound {len(replays)} replay files ready for analysis")
    else:
        print("\n✗ Download failed. Check your Kaggle setup.")
