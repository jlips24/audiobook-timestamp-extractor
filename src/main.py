from src.utils import seconds_to_hms
import argparse
import sys
import os
from .utils import setup_logging, get_logger
from .epub_parser import EpubParser
from .models import Chapter

logger = get_logger("Main")

def verify_chapters(chapters: list[Chapter]) -> list[Chapter]:
    """
    Phase 2: User Verification.
    Displays candidates and asks user to ignore specific IDs.
    """
    print("\n" + "="*60)
    print(f"FOUND {len(chapters)} CANDIDATE CHAPTERS")
    print("="*60)
    print(f"{'ID':<5} | {'TITLE':<40} | {'SEARCH PHRASE (Start)':<50}")
    print("-" * 100)
    
    for chap in chapters:
        snippet = (chap.search_phrase[:45] + "...") if len(chap.search_phrase) > 45 else chap.search_phrase
        print(f"{chap.index:<5} | {chap.toc_title[:38]:<40} | {snippet:<50}")
        
    print("-" * 100)
    print("\nReview the list above.")
    print("Enter the IDs of chapters to IGNORE (comma separated, e.g., '1, 2, 9').")
    print("Press ENTER to accept all.")
    
    user_input = input("> ").strip()
    
    if not user_input:
        logger.info("No chapters ignored.")
        return chapters
        
    try:
        ignore_ids = [int(x.strip()) for x in user_input.split(",") if x.strip().isdigit()]
    except ValueError:
        logger.error("Invalid input. Please enter numbers only.")
        return verify_chapters(chapters) # Recursive retry
        
    ignored_count = 0
    for chap in chapters:
        if chap.index in ignore_ids:
            chap.status = "IGNORED"
            ignored_count += 1
            
    logger.info(f"Ignored {ignored_count} chapters based on user input.")
    
    # Return only active chapters for next steps
    active_chapters = [c for c in chapters if c.status != "IGNORED"]
    return active_chapters

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
    parser = EpubParser(args.epub)
    chapters = parser.parse()
    
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
    
    from .audio_analyzer import AudioAnalyzer
    import json

    logger.info("Starting Phase 4: Audio Analysis (Linear Forward Scan)")
    
    analyzer = AudioAnalyzer(args.audio, model_size="medium")
    # Optional: get duration if needed for logging, though analyzer.get_duration() is called inside linear scan too.
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
    output_data = []
    
    # Intro Check (Phase 5 logic from Plan)
    # If first valid chapter starts significantly > 0, insert Intro
    # AND we have a confirm on it
    if valid_chapters and valid_chapters[0].status == "FOUND":
        first_chap = valid_chapters[0]
        if first_chap.confirmed_time and first_chap.confirmed_time > 10.0:
            logger.info("First chapter starts > 10s. Inserting INTRO chapter at 0:00.")
            output_data.append({
                "title": "Intro / Prologue",
                "start_time": "00:00:00",
                "seconds": 0
            })
            
    for chap in valid_chapters:
        if chap.status == "FOUND" and chap.confirmed_time is not None:
            # Floor to integer (drop decimals)
            seconds_int = int(chap.confirmed_time)
            
            m, s = divmod(seconds_int, 60)
            h, m = divmod(m, 60)
            
            # Format HH:MM:SS (no decimals)
            time_str = f"{h:02d}:{m:02d}:{s:02d}"
            
            output_data.append({
                "title": chap.toc_title,
                "start_time": time_str,
                "seconds": seconds_int
            })
        else:
            # Includes chapters not found with blank timestamps
            output_data.append({
                "title": chap.toc_title,
                "start_time": "",
                "seconds": ""
            })
            
    # -- Output Directory Logic --
    metadata = parser.get_metadata()
    # Sanitize filenames logic
    def sanitize(s):
        return "".join(c for c in s if c.isalnum() or c in (' ', '-', '_')).strip()
        
    author = sanitize(metadata.get('author', 'Unknown Author'))
    title = sanitize(metadata.get('title', 'Unknown Title'))
    
    # Create "repo/{Author} - {Title}"
    import pathlib
    repo_dir = pathlib.Path("repo") / f"{author} - {title}"
    repo_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. JSON
    json_path = repo_dir / "chapter_timestamps.json"
    with open(json_path, "w") as f:
        json.dump(output_data, f, indent=4)
        
    # 2. Markdown Table
    md_path = repo_dir / "chapter_timestamps.md"
    with open(md_path, "w") as f:
        f.write(f"# Chapter Timestamps\n")
        f.write(f"**Book:** {title}\n")
        f.write(f"**Author:** {author}\n\n")
        f.write(f"| Chapter | Start Time | Seconds |\n")
        f.write(f"| :--- | :--- | :--- |\n")
        for item in output_data:
            f.write(f"| {item['title']} | {item['start_time']} | {item['seconds']} |\n")
        
    logger.info(f"\nProcessing complete. Found {confirmed_count} chapters.")
    logger.info(f"Results saved to:\n  - {json_path}\n  - {md_path}")

if __name__ == "__main__":
    main()
