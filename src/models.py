from dataclasses import dataclass
from typing import Optional


@dataclass
class Chapter:
    """
    Represents a chapter or significant section in the book.
    Tracks its state from discovery in EPUB to timestamp confirmation in Audio.
    """
    index: int                          # Internal ID (0, 1, 2...)
    toc_title: str                      # Title from EPUB Table of Contents
    search_phrase: str                  # First paragraph/sentence for matching
    alternate_phrase: str = ""          # Fallback phrase if primary is weak
    word_count: int = 0                 # Total words in this chapter/section
    word_offset: int = 0                # Cumulative word count start
    estimated_time: float = 0.0         # Heuristic start time (seconds)
    confirmed_time: Optional[float] = None  # Confirmed start time (seconds)
    status: str = "PENDING"             # PENDING, IGNORED, FOUND, FAILED, INSERTED

    def __repr__(self):
        return (f"<Chapter {self.index}: '{self.toc_title}' "
                f"Status={self.status} Time={self.confirmed_time}>")
