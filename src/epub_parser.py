from typing import List

from bs4 import BeautifulSoup
from ebooklib import epub

from .models import Chapter
from .utils import get_logger

logger = get_logger(__name__)


class EpubParser:
    def __init__(self, epub_path: str):
        self.epub_path = epub_path
        self.book = None
        self.chapters: List[Chapter] = []

    def load(self):
        """Loads the EPUB file."""
        logger.info(f"Loading EPUB: {self.epub_path}")
        try:
            self.book = epub.read_epub(self.epub_path)
            # monkey patch for older ebooklib versions sometimes needing this
            # or just to be safe
        except Exception as e:
            logger.error(f"Failed to load EPUB: {e}")
            raise

    def parse(self) -> List[Chapter]:
        """
        Parses the EPUB TOC and extracts chapter information.
        Returns a list of Chapter objects.
        """
        if not self.book:
            self.load()

        logger.info("Parsing Table of Contents...")

        # Flatten the TOC (it can be nested)
        # ebooklib TOC items are either epub.Link, epub.Section, or tuple/list
        flat_toc = self._flatten_toc(self.book.toc)

        chapter_index = 1  # Start at 1, 0 reserved for potential Intro

        for item in flat_toc:
            # We only care about Links that point to actual content
            if not isinstance(item, epub.Link):
                continue

            href = item.href.split('#')[0]  # Remove anchors
            title = item.title

            # Find the actual item in the book
            doc = self.book.get_item_with_href(href)
            if not doc:
                logger.warning(f"TOC Link '{title}' points to missing href: {href}")
                continue

            # Parse content
            soup = BeautifulSoup(doc.get_content(), 'html.parser')

            # Heuristic: Check word count to filter out Images / Empty pages
            text_content = soup.get_text()
            word_count = len(text_content.split())

            if word_count < 50:
                logger.debug(f"Skipping '{title}': Word count {word_count} < 50")
                continue

            # Extract Search Phrase
            phrase, alt_phrase = self._extract_search_phrases(soup)

            if not phrase:
                logger.warning(f"Could not extract phrase for '{title}'")
                continue

            # Create Chapter
            chap = Chapter(
                index=chapter_index,
                toc_title=title,
                search_phrase=phrase,
                alternate_phrase=alt_phrase,
                word_count=word_count,
                word_offset=0,  # To be calculated later
                status="PENDING"
            )
            self.chapters.append(chap)
            # logger.info(f"Found Candidate: {chap.index} - {chap.toc_title}")
            chapter_index += 1

        return self.chapters

    def _flatten_toc(self, toc):
        """Recursively flattens the Table of Contents."""
        flat = []
        for item in toc:
            if isinstance(item, (list, tuple)):
                # Section tuple (SectionTitle, [Children])
                # We generally care about the children
                # Depending on ebooklib version, structure varies
                # Recursively add children
                for sub in item:
                    if isinstance(sub, list):
                        flat.extend(self._flatten_toc(sub))
                    else:
                        flat.append(sub)
            else:
                flat.append(item)
        return flat

    def _extract_search_phrases(self, soup: BeautifulSoup) -> tuple[str, str]:
        """
        Extracts the first narrative paragraph.
        Returns (primary_phrase, alternate_phrase).
        """
        # Remove headers
        for header in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            header.decompose()

        paragraphs = soup.find_all('p')
        valid_paragraphs = []

        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 20:  # Arbitrary filter for "Chapter 1" text in <p>
                valid_paragraphs.append(text)

        if not valid_paragraphs:
            return "", ""

        paragraph_length_limit = 150
        primary = self._safe_truncate(valid_paragraphs[0], paragraph_length_limit)
        secondary = ""

        if len(primary) < 50 and len(valid_paragraphs) > 1:
            # Combine if first is short
            combined = valid_paragraphs[0] + " " + valid_paragraphs[1]
            primary = self._safe_truncate(combined, paragraph_length_limit)
        elif len(valid_paragraphs) > 1:
            secondary = self._safe_truncate(valid_paragraphs[1], paragraph_length_limit)

        return primary, secondary

    def _safe_truncate(self, text: str, limit: int) -> str:
        """
        Truncates text to limit, but extends to the next whitespace
        to avoid cutting words in half.
        """
        if len(text) <= limit:
            return text

        # If the character at limit is a space, simply cut there (or trim)
        # Actually simplest is: scan from limit forward until space or end
        end = limit
        while end < len(text) and not text[end].isspace():
            end += 1

        return text[:end]

    def get_metadata(self) -> dict:
        """
        Extracts metadata (Author, Title) from the EPUB.
        Returns a dictionary with 'author' and 'title'.
        """
        if not self.book:
            self.load()

        # Helper to get DC text safely
        def get_dc(name):
            try:
                # ebooklib uses get_metadata('DC', 'name') returning a list of tuples usually
                items = self.book.get_metadata('DC', name)
                if items and len(items) > 0:
                    return items[0][0]
            except Exception:
                pass
            return "Unknown"

        title = get_dc('title')
        author = get_dc('creator')

        return {
            "title": title,
            "author": author
        }
