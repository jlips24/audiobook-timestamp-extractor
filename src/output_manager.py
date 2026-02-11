import json
import pathlib

from .utils import get_logger

# import subprocess


logger = get_logger("OutputManager")


def get_output_dir(final_author, final_title, final_audible_id):
    """
    Returns the Path object for the book's output directory.
    Format: repo/{Author}/{Title} [{AudibleID}]
    """
    base_repo = pathlib.Path("repo")
    author_dir = base_repo / final_author
    book_dir_name = f"{final_title} [{final_audible_id}]"
    return author_dir / book_dir_name


def save_results(valid_chapters, final_author, final_title, final_audible_id):
    """
    Formats the results and saves them to JSON and Markdown files.
    """
    output_data = []

    # Intro Check (Phase 5 logic)
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

    found_count = 0
    for chap in valid_chapters:
        if chap.status == "FOUND" and chap.confirmed_time is not None:
            found_count += 1
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

    # -- Output Directory Logic --
    output_dir = get_output_dir(final_author, final_title, final_audible_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. JSON
    json_path = output_dir / "chapter_timestamps.json"
    with open(json_path, "w") as f:
        json.dump(output_data, f, indent=4)

    # 2. Markdown Table
    md_path = output_dir / "chapter_timestamps.md"
    with open(md_path, "w") as f:
        f.write("# Chapter Timestamps\n")
        f.write(f"**Book:** {final_title}\n")
        f.write(f"**Author:** {final_author}\n")
        f.write(f"**Audible ID:** {final_audible_id}\n\n")
        f.write("| Chapter | Start Time | Seconds |\n")
        f.write("| :--- | :--- | :--- |\n")
        for item in output_data:
            f.write(f"| {item['title']} | {item['start_time']} | {item['seconds']} |\n")

    logger.info(f"\nProcessing complete. Found {found_count} chapters.")
    logger.info(f"Results saved to:\n  - {json_path}\n  - {md_path}")
