import json
import re
import pathlib
import sys
from typing import List, Dict

from .utils import get_logger, seconds_to_hms

logger = get_logger("SyncLogic")


def parse_timestamp_to_seconds(ts_str: str) -> float:
    """Converts HH:MM:SS or MM:SS to seconds float."""
    if not ts_str:
        return 0.0
    parts = ts_str.strip().split(":")
    seconds = 0
    if len(parts) == 3:
        h, m, s = map(int, parts)
        seconds = h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = map(int, parts)
        seconds = m * 60 + s
    return float(seconds)


def sync_md_to_json(project_dir: pathlib.Path):
    """
    Reads chapter_timestamps.md and overwrites chapter_timestamps.json
    """
    md_path = project_dir / "chapter_timestamps.md"
    json_path = project_dir / "chapter_timestamps.json"
    
    if not md_path.exists():
        logger.error(f"Markdown file not found: {md_path}")
        return

    logger.info(f"Reading MD: {md_path} -> Syncing to JSON")
    
    chapters = []
    
    with open(md_path, "r") as f:
        lines = f.readlines()
        
    # Parse Table
    # Expected format: | Chapter | Start Time | Seconds |
    # We skip lines until we start seeing pipe chars
    
    in_table = False
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
            
        # Check if header or separator
        if "---" in stripped or "Start Time" in stripped:
            in_table = True
            continue
            
        if in_table:
            # Parse row
            # | Title | HH:MM:SS | SSSS |
            parts = [p.strip() for p in stripped.split("|") if p.strip()]
            
            if len(parts) < 2:
                continue
                
            title = parts[0]
            start_time_str = parts[1]
            
            # Recalculate seconds from the Time String to trust the human edit
            # (Ignore the 3rd column 'Seconds', re-derive it)
            if start_time_str:
                seconds = parse_timestamp_to_seconds(start_time_str)
                chapters.append({
                    "title": title,
                    "start_time": start_time_str,
                    "seconds": int(seconds)
                })
            else:
                # Handle empty case
                chapters.append({
                    "title": title,
                    "start_time": "",
                    "seconds": ""
                })

    if not chapters:
        logger.warning("No chapters found in Markdown table.")
        return

    with open(json_path, "w") as f:
        json.dump(chapters, f, indent=4)
        
    logger.info(f"✅ Synced {len(chapters)} chapters to JSON.")


def sync_json_to_md(project_dir: pathlib.Path):
    """
    Reads chapter_timestamps.json and updates chapter_timestamps.md.
    Preserves existing MD headers if possible.
    """
    md_path = project_dir / "chapter_timestamps.md"
    json_path = project_dir / "chapter_timestamps.json"

    if not json_path.exists():
        logger.error(f"JSON file not found: {json_path}")
        return
        
    with open(json_path, "r") as f:
        data = json.load(f)
        
    # Read existing MD to preserve header
    header_lines = []
    if md_path.exists():
        with open(md_path, "r") as f:
            for line in f:
                # Stop at table header
                if "| Chapter | Start Time" in line:
                    break
                header_lines.append(line)
    else:
        # Default header if missing
        # We try to guess metadata from folder name
        # Ideally we extracted this in repo_manager but we can just use defaults
        header_lines.append("# Chapter Timestamps\n\n")
        
    # Write New MD
    with open(md_path, "w") as f:
        f.writelines(header_lines)
        if not header_lines or not header_lines[-1].strip().startswith("|"):
             # Ensure we didn't leave a partial table header
             pass
        
        # Write Table Header Logic
        # We need to make sure we don't duplicate headers if they were in header_lines
        # The logic above stopped *before* the table header, so we write a fresh one.
        
        f.write("| Chapter | Start Time | Seconds |\n")
        f.write("| :--- | :--- | :--- |\n")
        
        for item in data:
            title = item.get("title", "Unknown")
            start_time = item.get("start_time", "")
            seconds = item.get("seconds", "")
            
            # Recalculate formatted string if missing but seconds present?
            # Or trust JSON. Let's trust JSON but fallback.
            if not start_time and seconds and isinstance(seconds, (int, float)):
                 start_time = seconds_to_hms(int(seconds))
            
            f.write(f"| {title} | {start_time} | {seconds} |\n")
            
    logger.info(f"✅ Synced {len(data)} chapters to Markdown.")
