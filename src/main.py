import argparse
import os
import sys

from src.utils import get_logger, seconds_to_hms, setup_logging

from .audio_analyzer import AudioAnalyzer
from .epub_parser import EpubParser
from .output_manager import save_results
from .user_interaction import get_book_metadata, verify_chapters

logger = get_logger("Main")


def main():
    parser = argparse.ArgumentParser(description="Audiobook Chapter Syncer")
    parser.add_argument("epub", nargs='?', help="Path to the source EPUB file (Optional for sync modes)")
    parser.add_argument("audio", nargs='?', help="Path to the source M4B/MP3 audiobook file (Optional for sync modes)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--find-missing", action="store_true", help="Scan only for missing chapters based on existing output")
    parser.add_argument("--sync-md-to-json", action="store_true", help="Update JSON from manual edits in Markdown")
    parser.add_argument("--sync-json-to-md", action="store_true", help="Update Markdown table from JSON data")
    
    args = parser.parse_args()

    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)
    
    # Check for Sync Modes first (they don't need files)
    if args.sync_md_to_json or args.sync_json_to_md:
        run_sync_mode(args)
        sys.exit(0)
    
    if args.find_missing:
        # Route to find missing mode
        # Fix: find_missing mode DOES require files because it runs analysis
        if not args.epub or not args.audio:
             logger.error("Find Missing mode requires EPUB and Audio file paths.")
             sys.exit(1)
        run_find_missing_mode(args)
        sys.exit(0)

    if not args.epub or not args.audio:
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(args.epub):

        logger.error(f"EPUB file not found: {args.epub}")
        sys.exit(1)

    if not os.path.exists(args.audio):
        logger.error(f"Audio file not found: {args.audio}")
        sys.exit(1)

    # --- Phase 1: Parsing ---
    logger.info("Starting Phase 1: EPUB Extraction")
    epub_parser = EpubParser(args.epub)

    # -- Metadata Configuration & User Prompts --
    final_author, final_title, final_audible_id = get_book_metadata(epub_parser)

    chapters = epub_parser.parse()

    if not chapters:
        logger.error("No chapters found in EPUB. Exiting.")
        sys.exit(1)

    # --- Phase 2: Verification ---
    logger.info("Starting Phase 2: User Verification")
    valid_chapters = verify_chapters(chapters)

    if not valid_chapters:
        logger.warning("All chapters were ignored! Exiting.")
        sys.exit(0)

    logger.info(f"Proceeding with {len(valid_chapters)} valid chapters.")

    logger.info("Starting Phase 4: Audio Analysis (Linear Forward Scan)")

    analyzer = AudioAnalyzer(args.audio, model_size="medium")
    duration = analyzer.get_duration()
    logger.info(f"Audio Duration: {seconds_to_hms(int(duration))} seconds")

    # Confirm Chapter 1 first to anchor (or first valid chapter)
    # We loop through candidates

    confirmed_count = 0
    last_confirmed_time = 0.0
    default_search_window = 2700  # Start with 45 minutes
    current_search_window = default_search_window

    for i, chap in enumerate(valid_chapters):
        logger.info(f"Processing Chapter {chap.index}: '{chap.toc_title}'")

        # Search using linear scan from last confirmed time
        found = analyzer.find_chapter_linear(
            chap,
            last_confirmed_time,
            max_search_duration=current_search_window
        )

        if found:
            confirmed_count += 1
            if chap.confirmed_time:
                last_confirmed_time = chap.confirmed_time

            # Success: Reset search window to default
            if current_search_window > default_search_window:
                logger.info(
                    f"Resetting search window to {int(default_search_window / 60)} minutes."
                )
                current_search_window = default_search_window
        else:
            logger.warning(f"Could not confirm Chapter {chap.index}.")
            # Failure: Expand search window for next chapter search
            current_search_window += default_search_window
            logger.info(
                f"Expanding search window to {int(current_search_window / 60)}"
                "minutes for next chapter."
            )
            # last_confirmed_time remains the same (searching from same anchor)

    # --- Phase 5: Output ---
    save_results(valid_chapters, final_author, final_title, final_audible_id)


def run_find_missing_mode(args):
    """
    Separate entry point for finding missing chapters.
    """
    from src.find_missing import interactive_find_setup

    logger.info("Running in FIND MISSING mode.")
    
    if not os.path.exists(args.epub):
        logger.error(f"EPUB file not found: {args.epub}")
        sys.exit(1)
    if not os.path.exists(args.audio):
        logger.error(f"Audio file not found: {args.audio}")
        sys.exit(1)

    epub_parser = EpubParser(args.epub)
    
def run_sync_mode(args):
    """
    Entry point for synchronization utilities.
    """
    from src.repo_manager import interactive_find_project_dir
    from src.sync_logic import sync_md_to_json, sync_json_to_md

    project_dir = interactive_find_project_dir()
    if not project_dir:
        sys.exit(1)

    if args.sync_md_to_json:
        sync_md_to_json(project_dir)
    elif args.sync_json_to_md:
        sync_json_to_md(project_dir)


if __name__ == "__main__":
    main()



if __name__ == "__main__":
    main()
