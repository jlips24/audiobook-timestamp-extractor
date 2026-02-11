import json
import pathlib
from typing import List, Optional

from .audio_analyzer import AudioAnalyzer
from .models import Chapter
from .output_manager import get_output_dir, save_results
from .utils import get_logger

logger = get_logger("FixLogic")


def load_existing_timestamps(json_path: pathlib.Path) -> dict:
    """
    Loads timestamp data from JSON file.
    Returns a dict mapping chapter title to start_time (seconds).
    """
    if not json_path.exists():
        return {}

    try:
        with open(json_path, "r") as f:
            data = json.load(f)
        
        mapping = {}
        for item in data:
            title = item.get("title")
            time_str = item.get("start_time")
            if title and time_str:
                # Convert HH:MM:SS to seconds
                parts = time_str.split(":")
                if len(parts) == 3:
                    h, m, s = map(int, parts)
                    seconds = h * 3600 + m * 60 + s
                    mapping[title] = float(seconds)
        return mapping
    except Exception as e:
        logger.error(f"Failed to load existing stamps: {e}")
        return {}
import sys

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
    print("Please enter the Audible ID of the book (e.g. B00XXXXXXX).")
    
    audible_id = input("Audible ID: ").strip()
    
    if not audible_id:
        logger.error("Audible ID is required.")
        sys.exit(1)
        
    # Scan repo for this ID
    base_repo = pathlib.Path("repo")
    found_dir = None
    found_author = ""
    
    # We need to find `repo/{Author}/{Title} [{ID}]`
    # We can use glob on base_repo
    # Pattern: */*[{audible_id}]
    
    candidates = list(base_repo.glob(f"*/*[{audible_id}]"))
    
    if not candidates:
        logger.error(f"No project found in 'repo/' matching ID: {audible_id}")
        logger.info("Please ensure you have run the initial scan first.")
        sys.exit(1)
        
    if len(candidates) > 1:
        logger.warning(f"Multiple projects found for ID {audible_id}. Using the first one.")
        
    found_dir = candidates[0]
    # Structure: repo/{Author}/{Title} [{ID}]
    # Parent name is Author
    found_author = found_dir.parent.name
    # Dir name is Title [ID]
    dir_name = found_dir.name
    
    # Extract Title: everything before " [{ID}]"
    # Safety check
    suffix = f" [{audible_id}]"
    if dir_name.endswith(suffix):
        found_title = dir_name[:-len(suffix)]
    else:
        # Fallback if bracket format is weird, just take dir_name
        found_title = dir_name
        
    print(f"\nFound existing project:")
    print(f"  Author: {found_author}")
    print(f"  Title:  {found_title}")
    print(f"  ID:     {audible_id}")
    print("-" * 60)
    
    confirm = input("Is this correct? [y/N]: ").strip().lower()
    if confirm != 'y':
        logger.info("Aborted by user.")
        sys.exit(0)
        
    files_exist = (found_dir / "chapter_timestamps.json").exists()
    if not files_exist:
        logger.error("Project folder exists but 'chapter_timestamps.json' is missing.")
        sys.exit(1)
        
    # Proceed
    find_missing_chapters(epub_parser, audio_path, found_author, found_title, audible_id)


def find_missing_chapters(epub_parser, audio_path: str, author: str, title: str, audible_id: str):
    """
    Core logic to find missing chapters using existing data as anchors.
    """
    logger.info("Starting 'Find Missing' Mode...")

    # 1. Re-parse EPUB to get the master list of chapters
    #    (We need the search phrases which aren't in the JSON)
    chapters: List[Chapter] = epub_parser.parse()
    if not chapters:
        logger.error("No chapters found in EPUB.")
        return

    # 2. Load existing JSON results
    output_dir = get_output_dir(author, title, audible_id)
    json_path = output_dir / "chapter_timestamps.json"
    
    if not json_path.exists():
        logger.error(f"No existing results found at {json_path}. Cannot fix missing.")
        return

    logger.info(f"Loading existing results from {json_path}")
    existing_map = load_existing_timestamps(json_path)
    
    # 3. Merge: Mark chapters as FOUND if in JSON
    #    We match by Title. (Ideally we'd use index, but JSON structure is flat list)
    found_count = 0
    for chap in chapters:
        if chap.toc_title in existing_map:
            chap.status = "FOUND"
            chap.confirmed_time = existing_map[chap.toc_title]
            found_count += 1
        else:
            chap.status = "PENDING"
            chap.confirmed_time = None

    logger.info(f"Merged state: {found_count}/{len(chapters)} chapters found.")

    # 4. Initialize AudioAnalyzer
    analyzer = AudioAnalyzer(audio_path, model_size="medium")
    total_duration = analyzer.get_duration()
    logger.info(f"Audio Duration: {total_duration}s")

    # 5. Gap Search Loop
    # We iterate and find "islands" of MISSING chapters.
    # For a missing chapter C_i, we look for:
    #   Start Bound: Time of closest preceding FOUND chapter (or 0.0)
    #   End Bound: Time of closest following FOUND chapter (or total_duration)

    for i, chap in enumerate(chapters):
        if chap.status == "FOUND":
            continue

        logger.info(f"\nAttempting to find missing Chapter {chap.index}: '{chap.toc_title}'")

        # Find Start Bound (Previous Found)
        start_bound = 0.0
        for prev in reversed(chapters[:i]):
            if prev.status == "FOUND" and prev.confirmed_time is not None:
                start_bound = prev.confirmed_time
                break
        
        # Find End Bound (Next Found)
        end_bound = total_duration
        for nxt in chapters[i+1:]:
            if nxt.status == "FOUND" and nxt.confirmed_time is not None:
                end_bound = nxt.confirmed_time
                break

        search_window = end_bound - start_bound
        
        if search_window <= 0:
            logger.warning(
                f"Invalid search window for '{chap.toc_title}': "
                f"Start {start_bound} >= End {end_bound}. Skipping."
            )
            continue
            
        logger.info(
            f"Search Range: {int(start_bound)}s -> {int(end_bound)}s "
            f"(Window: {int(search_window)}s)"
        )

        # Use the existing linear scan, but constrained by max_search_duration
        # We start searching from `start_bound`
        # We limit search to `search_window` so it doesn't cross `end_bound`
        
        # Optimization: Scan slightly after start_bound to avoid re-matching the previous chapter
        # specific buffer can be tweaked. 5s is safe.
        actual_start = start_bound + 5.0
        actual_window = end_bound - actual_start

        if actual_window < 10:
             logger.warning("Gap too small (<10s). Skipping.")
             continue

        found = analyzer.find_chapter_linear(
            chap,
            start_search_time=actual_start,
            max_search_duration=actual_window
        )

        if found:
            logger.info("✅ Recovered missing chapter!")
        else:
            logger.info("❌ Couldn't recover missing chapter.")

    # 6. Save Updated Results
    logger.info("Saving updated results...")
    save_results(chapters, author, title, audible_id)
