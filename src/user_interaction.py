from .models import Chapter
from .utils import get_logger, sanitize

logger = get_logger("UserInteraction")


def verify_chapters(chapters: list[Chapter]) -> list[Chapter]:
    """
    Phase 2: User Verification.
    Displays candidates and asks user to ignore specific IDs.
    """
    print("\n" + "=" * 60)
    print(f"FOUND {len(chapters)} CANDIDATE CHAPTERS")
    print("=" * 60)
    print(f"{'ID':<5} | {'TITLE':<40} | {'SEARCH PHRASE (Start)':<50}")
    print("-" * 100)

    for chap in chapters:
        snippet = (
            chap.search_phrase[:45] + "..."
        ) if len(chap.search_phrase) > 45 else chap.search_phrase
        print(f"{chap.index:<5} | {chap.toc_title[:38]:<40} | {snippet:<50}")

    print("-" * 100)
    print("\nReview the list above.")
    print("Enter the IDs of chapters to IGNORE.")
    print("Supports comma-separated numbers and ranges (e.g., '1, 2, 5-8').")
    print("Press ENTER to accept all.")

    user_input = input("> ").strip()

    if not user_input:
        logger.info("No chapters ignored.")
        return chapters

    try:
        ignore_ids = set()
        parts = [p.strip() for p in user_input.split(",") if p.strip()]

        for part in parts:
            if "-" in part:
                # Range logic: "1-5"
                start_str, end_str = part.split("-", 1)
                start, end = int(start_str.strip()), int(end_str.strip())
                # Create range inclusive of end
                # Handle reverse range or single point if needed, but standard range(start, end+1)
                # works
                if start > end:
                    # Swap if user did 10-1
                    start, end = end, start
                ignore_ids.update(range(start, end + 1))
            else:
                # Single number
                ignore_ids.add(int(part))

    except ValueError:
        logger.error("Invalid input. Please enter numbers or ranges (e.g. '1-5') only.")
        return verify_chapters(chapters)  # Recursive retry

    ignored_count = 0
    for chap in chapters:
        if chap.index in ignore_ids:
            chap.status = "IGNORED"
            ignored_count += 1

    logger.info(f"Ignored {ignored_count} chapters based on user input.")

    # Return only active chapters for next steps
    active_chapters = [c for c in chapters if c.status != "IGNORED"]
    return active_chapters


def get_book_metadata(parser) -> tuple[str, str, str]:
    """
    Interactive prompt for book metadata.
    """
    metadata = parser.get_metadata()

    default_author = sanitize(metadata.get('author', 'Unknown Author'))
    default_title = sanitize(metadata.get('title', 'Unknown Title'))

    print("\n" + "=" * 60)
    print("METADATA CONFIGURATION")
    print("=" * 60)

    # Prompt for details
    author_input = input(f"Author [{default_author}]: ").strip()
    final_author = sanitize(author_input) if author_input else default_author

    title_input = input(f"Book Title [{default_title}]: ").strip()
    final_title = sanitize(title_input) if title_input else default_title

    audible_id = ""
    while not audible_id:
        audible_id = input("Audible ID (required): ").strip()
        if not audible_id:
            print("Audible ID is required. Please check the URL/Store page.")

    final_audible_id = sanitize(audible_id)
    print("-" * 60 + "\n")

    return final_author, final_title, final_audible_id
