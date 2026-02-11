import json
import pathlib
from typing import List, Optional

from .audio_analyzer import AudioAnalyzer
from .models import Chapter
from .output_manager import get_output_dir
from .sync_logic import sync_json_to_md
from .utils import get_logger, seconds_to_hms

logger = get_logger("FixLogic")


def load_existing_timestamps(json_path: pathlib.Path) -> List[dict]:
    """
    Loads timestamp data from JSON file.
    Returns a list of dicts: [{'title': '...', 'start_time': '...', 'seconds': ...}, ...]
    Preserves order from the file.
    """
    if not json_path.exists():
        return []

    try:
        with open(json_path, "r") as f:
            data = json.load(f)

        # Ensure we return valid list
        if not isinstance(data, list):
            return []

        return data
    except Exception as e:
        logger.error(f"Failed to load existing stamps: {e}")
        return []

import sys

from .repo_manager import interactive_find_project_dir, parse_project_dir


def interactive_find_setup(epub_parser, audio_path: str):
    """
    Interactive workflow to setup the find missing chapters process.
    1. Ask for Audible ID
    2. Validate against repo/
    3. Confirm Title/Author
    4. Run find
    """
    print("\n" + "=" * 60)
    print("FIND MISSING CHAPTERS MODE")
    print("=" * 60)
    print("This mode uses existing results in the 'repo/' folder as anchors.")

    project_dir = interactive_find_project_dir()
    if not project_dir:
        sys.exit(1)

    author, title, audible_id = parse_project_dir(project_dir)

    files_exist = (project_dir / "chapter_timestamps.json").exists()
    if not files_exist:
        logger.error("Project folder exists but 'chapter_timestamps.json' is missing.")
        sys.exit(1)

    # Proceed
    find_missing_chapters(epub_parser, audio_path, author, title, audible_id)


def find_missing_chapters(epub_parser, audio_path: str, author: str, title: str, audible_id: str):
    """
    Core logic to find missing chapters using existing JSON data as the master list.
    """
    logger.info("Starting 'Find Missing' Mode...")

    # 1. Parse EPUB to get Search Phrases (Lookup Map)
    epub_chapters: List[Chapter] = epub_parser.parse()
    if not epub_chapters:
        logger.error("No chapters found in EPUB.")
        return

    # Map: Title -> Chapter Object (contains search_phrase)
    epub_map = {c.toc_title: c for c in epub_chapters}

    # 2. Load existing JSON results
    output_dir = get_output_dir(author, title, audible_id)
    json_path = output_dir / "chapter_timestamps.json"

    if not json_path.exists():
        logger.error(f"No existing results found at {json_path}. Cannot fix missing.")
        return

    logger.info(f"Loading existing results from {json_path}")
    existing_data = load_existing_timestamps(json_path)

    if not existing_data:
        logger.warning("Existing JSON is empty or invalid.")
        return

    # 3. Analyze Audio
    analyzer = AudioAnalyzer(audio_path, model_size="medium")
    total_duration = analyzer.get_duration()
    logger.info(f"Audio Duration: {total_duration}s")

    # 4. Iterate and Find Missing
    # We maintain 'last_confirmed_time' to serve as the start anchor for gaps.

    updates_made = False

    # Pre-process: Calculate start/end bounds for each item?
    # Simpler: Just iterate. If missing, look ahead for next found to determine window.

    for i, item in enumerate(existing_data):
        item_title = item.get("title")
        item_seconds = item.get("seconds")

        # Check if "FOUND" (has valid seconds)
        is_found = False
        if item_seconds is not None and item_seconds != "":
            try:
                # Ensure it's a number
                float(item_seconds)
                is_found = True
            except ValueError:
                is_found = False

        if is_found:
            continue

        # --- It's MISSING. Perform Search. ---
        logger.info(f"\nAttempting to find missing Chapter: '{item_title}'")

        # 4a. Get Search Phrase from EPUB
        if item_title not in epub_map:
            logger.warning(f"  [Skip] Title '{item_title}' not found in EPUB. Cannot determine search phrase.")
            continue

        epub_chap = epub_map[item_title]
        # We need a Chapter object for the analyzer.
        # We can reuse the one from EPUB but we should verify index/title match?
        # Actually, analyzer only needs search_phrase and index (for logging).

        # 4b. Determine Search Window
        # Start Bound: Closest preceding FOUND chapter
        start_bound = 0.0
        for prev in reversed(existing_data[:i]):
            s = prev.get("seconds")
            if s is not None and s != "":
                try:
                    start_bound = float(s)
                    break
                except ValueError:
                    pass

        # End Bound: Closest following FOUND chapter
        end_bound = total_duration
        for nxt in existing_data[i+1:]:
            s = nxt.get("seconds")
            if s is not None and s != "":
                try:
                    end_bound = float(s)
                    break
                except ValueError:
                    pass

        search_window = end_bound - start_bound

        if search_window <= 0:
            logger.warning(f"  [Skip] Invalid window: Start {start_bound} >= End {end_bound}")
            continue

        logger.info(
            f"  Search Range: {seconds_to_hms(int(start_bound))} -> {seconds_to_hms(int(end_bound))} "
            f"(Window: {int(search_window)}s)"
        )

        # Optimization: Buffer (same as before)
        actual_start = start_bound + 5.0
        actual_window = end_bound - actual_start

        if actual_window < 10:
             logger.warning("  [Skip] Gap too small (<10s).")
             continue

        # 4c. Run Search
        found = analyzer.find_chapter_linear(
            epub_chap, # Pass the EPUB chapter object which has the search phrase
            start_search_time=actual_start,
            max_search_duration=actual_window
        )

        if found and epub_chap.confirmed_time is not None:
             logger.info(f"  ✅ Found at {epub_chap.confirmed_time}s")
             # Update the JSON item
             item["seconds"] = int(epub_chap.confirmed_time)
             item["start_time"] = seconds_to_hms(int(epub_chap.confirmed_time))
             updates_made = True
        else:
             logger.info("  ❌ Not found.")

    # 5. Save Updated Results
    if updates_made:
        logger.info("Saving updated results...")

        try:
            with open(json_path, "w") as f:
                json.dump(existing_data, f, indent=4)
            logger.info("✅ JSON updated.")

            # Sync to Markdown
            sync_json_to_md(output_dir)

        except Exception as e:
            logger.error(f"Failed to save JSON: {e}")
    else:
        logger.info("No new chapters found.")
