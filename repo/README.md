# Repository Structure and Contribution Guide

This directory contains the community-contributed chapter timestamps for various audiobooks. These timestamps are used to help others navigate their audiobooks with accurate chapter markers.

## File Structure

The repository is organized by author and then by book title:

```text
repo/
└── <Author Name>/
    └── <Book Title> [<Audible ID>]/
        ├── chapter_timestamps.json
        └── README.md
```

- **`chapter_timestamps.json`**: A machine-readable JSON file containing the chapter titles, start times, and total seconds.
- **`README.md`**: A human-readable Markdown file containing the same information in a table format, along with book metadata. This file is automatically rendered by platforms like GitHub when viewing the book directory.

## Contributing Process

To contribute new timestamps or update existing ones, please follow this process:

1.  **Run Audio Extraction**: Use the tool to generate the initial timestamps.
2.  **Fix Missing Chapters**: If the tool missed any chapters, run the "find missing" mode to interactively locate them.
3.  **Verify Title Names**: Ensure the chapter titles match the book's Table of Contents.
4.  **Verify Chapter Markers**: Manually verify that the chapter markers are in the correct place by comparing the timestamped audio to the actual words of the book.
5.  **Sync Files**: If you made manual changes to either the JSON or the Markdown file, use the sync commands to ensure both files are up-to-date.
6.  **Submit PR**: Create a Pull Request with your new or updated files.

## Common Commands

Below are the commands you'll likely need during the contribution process.

### Audio Extraction
Run the initial analysis to extract timestamps from an EPUB and its corresponding audiobook file.
```bash
python3 -m src.main <path_to_epub> <path_to_audio>
```

### Fix Missing Chapters
If some chapters were not found during the initial run, use this mode to search for them specifically.
```bash
python3 -m src.main <path_to_epub> <path_to_audio> --find-missing
```

### Synchronizing Files
If you manually edit the Markdown file (e.g., to fix a typo in a title), sync the changes back to the JSON file:
```bash
python3 -m src.main --sync-md-to-json
```

Conversely, if you edit the JSON file, sync the changes to the Markdown table:
```bash
python3 -m src.main --sync-json-to-md
```

*Note: The sync commands will prompt you to select the book directory you wish to synchronize.*
