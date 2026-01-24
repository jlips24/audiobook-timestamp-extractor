import argparse
import sys
import os
from src.utils import seconds_to_hms, setup_logging, get_logger
from .epub_parser import EpubParser
from .audio_analyzer import AudioAnalyzer
from .user_interaction import verify_chapters, get_book_metadata
from .output_manager import save_results

logger = get_logger("Main")

def main():
    parser = argparse.ArgumentParser(description="Audiobook Chapter Syncer")
    parser.add_argument("epub", help="Path to the source EPUB file")
    parser.add_argument("audio", help="Path to the source M4B/MP3 audiobook file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)
    
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
    default_search_window = 2700 # Start with 45 minutes
    current_search_window = default_search_window
    
    for i, chap in enumerate(valid_chapters):
        logger.info(f"Processing Chapter {chap.index}: '{chap.toc_title}'")
        
        # Search using linear scan from last confirmed time
        found = analyzer.find_chapter_linear(chap, last_confirmed_time, max_search_duration=current_search_window)
        
        if found:
            confirmed_count += 1
            if chap.confirmed_time:
                last_confirmed_time = chap.confirmed_time
                
            # Success: Reset search window to default
            if current_search_window > default_search_window:
                logger.info(f"Resetting search window to {int(default_search_window/60)} minutes.")
                current_search_window = default_search_window
        else:
            logger.warning(f"Could not confirm Chapter {chap.index}.")
            # Failure: Expand search window for next chapter search
            current_search_window += default_search_window
            logger.info(f"Expanding search window to {int(current_search_window/60)} minutes for next chapter.")
            # last_confirmed_time remains the same (searching from same anchor)

    # --- Phase 5: Output ---
    save_results(valid_chapters, final_author, final_title, final_audible_id)

if __name__ == "__main__":
    main()
