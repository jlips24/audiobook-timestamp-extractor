import unittest
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup
from ebooklib import epub

from src.epub_parser import EpubParser


class TestEpubParser(unittest.TestCase):

    @patch('src.epub_parser.epub.read_epub')
    def test_load_epub_success(self, mock_read_epub):
        mock_book = MagicMock()
        mock_read_epub.return_value = mock_book

        parser = EpubParser("dummy.epub")
        parser.load()

        self.assertIsNotNone(parser.book)
        mock_read_epub.assert_called_with("dummy.epub")

    def test_extract_search_phrases_simple(self):
        html = (
            "<html><body><h1>Chapter 1</h1><p>First paragraph is now definitely long enough "
            "to pass the fifty character threshold without combining.</p><p>Second paragraph is "
            "also long enough.</p></body></html>"
        )
        soup = BeautifulSoup(html, 'html.parser')

        # We need to access the private method for testing, or expose it.
        # Accessing protected method for unit testing is acceptable in Python.
        parser = EpubParser("dummy.epub")
        primary, secondary = parser._extract_search_phrases(soup)

        self.assertEqual(
            primary,
            "First paragraph is now definitely long enough to pass the fifty character threshold "
            "without combining."
        )
        self.assertEqual(secondary, "Second paragraph is also long enough.")

    def test_extract_search_phrases_short_first(self):
        # First paragraph is too short, should be combined with second
        html = "<html><body><p>Hi.</p><p>This is the real start.</p></body></html>"
        soup = BeautifulSoup(html, 'html.parser')

        parser = EpubParser("dummy.epub")
        primary, secondary = parser._extract_search_phrases(soup)

        # Note: logic in code is: if len(primary) < 50 and len > 1: primary = p1 + " " + p2
        # "Hi." is 3 chars. "This is the real start." is > 20 chars? 23 chars.
        # Wait, the logic also filters paragraphs < 20 chars initially!
        # "Hi." < 20 chars, so it will be filtered out completely in _extract_search_phrases loop.

        # Let's adjust test case to match logic:
        # P1 > 20 chars but < 50 chars.
        p1 = "Short but valid paragraph."  # 26 chars
        p2 = "This is the second paragraph that is longer."

        html = f"<html><body><p>{p1}</p><p>{p2}</p></body></html>"
        soup = BeautifulSoup(html, 'html.parser')

        primary, secondary = parser._extract_search_phrases(soup)

        self.assertEqual(primary, f"{p1} {p2}"[:150])

    def test_extract_search_phrases_word_boundary(self):
        """Test that truncation respects word boundaries."""
        # Create a paragraph where the 150th char is inside a word.
        # "Word " is 5 chars.
        # 30 "Word "s = 150 chars.
        # Let's make it so 150 lands in "Target".
        prefix = "Word " * 29  # 145 chars
        # Next word is "Target", starts at 145, ends at 151.
        # 150th char is 'e' in Target.
        text = prefix + "Target is here."

        html = f"<html><body><p>{text}</p></body></html>"
        soup = BeautifulSoup(html, 'html.parser')

        parser = EpubParser("dummy.epub")
        primary, _ = parser._extract_search_phrases(soup)

        # Expect "Target" to be fully included.
        # Length should be 145 + 6 = 151.
        expected = prefix + "Target"
        self.assertEqual(primary, expected)

    def test_get_metadata(self):
        """Test extraction of Title and Author."""
        parser = EpubParser("dummy.epub")
        parser.book = MagicMock()

        # Mock get_metadata('DC', 'key') -> [('Value',)]
        def mock_get_metadata_side_effect(namespace, name):
            if namespace == 'DC':
                if name == 'title':
                    return [('Test Book Title',)]
                if name == 'creator':
                    return [('Test Author',)]
            return []

        parser.book.get_metadata.side_effect = mock_get_metadata_side_effect

        metadata = parser.get_metadata()

        self.assertEqual(metadata['title'], 'Test Book Title')
        self.assertEqual(metadata['author'], 'Test Author')

    def test_flatten_toc_nested(self):
        """Test flattening of nested TOC structures."""
        # TOC structure: [Link1, (Section, [Link2, Link3]), Link4]
        link1 = epub.Link("1.html", "Chap 1", "id1")
        link2 = epub.Link("2.html", "Chap 2", "id2")
        link3 = epub.Link("3.html", "Chap 3", "id3")
        link4 = epub.Link("4.html", "Chap 4", "id4")

        toc = [
            link1,
            (epub.Section("Section 1"), [link2, link3]),
            link4
        ]

        parser = EpubParser("dummy.epub")
        flat = parser._flatten_toc(toc)

        # Expect 5 items: link1, Section, link2, link3, link4
        self.assertEqual(len(flat), 5)
        self.assertEqual(flat[0], link1)
        self.assertIsInstance(flat[1], epub.Section)
        self.assertEqual(flat[2], link2)
        self.assertEqual(flat[3], link3)
        self.assertEqual(flat[4], link4)

    @patch('src.epub_parser.BeautifulSoup')
    def test_parse_logic(self, mock_bs):
        """Test parse method filtering and chapter creation."""
        parser = EpubParser("dummy.epub")
        parser.book = MagicMock()
        parser.load = MagicMock()

        # Setup TOC
        link1 = epub.Link("chap1.html", "Chapter 1", "id1")
        parser.book.toc = [link1]

        # Setup Item lookup
        mock_item = MagicMock()
        mock_item.get_content.return_value = b"<html>Content</html>"
        parser.book.get_item_with_href.return_value = mock_item

        # Mock BeautifulSoup behavior
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup

        # Scenario 1: Short content (should be skipped)
        mock_soup.get_text.return_value = "Word " * 10  # 10 words

        chapters = parser.parse()
        self.assertEqual(len(chapters), 0)

        # Scenario 2: Long content (should be processed)
        mock_soup.get_text.return_value = "Word " * 100  # 100 words

        # Mock phrase extraction
        # We also need to mock _extract_search_phrases via the class or instance,
        # but since it's a method on the instance we are testing, we can mock it on the instance
        # or just rely on the BeautifulSoup mock structure if we didn't mock extraction.
        # Ideally we stick to mocking dependencies.
        # Let's mock the private method to isolate 'parse' logic.

        with patch.object(
            parser,
            '_extract_search_phrases',
            return_value=("Start phrase", "Alt phrase")
        ):
            chapters = parser.parse()
            self.assertEqual(len(chapters), 1)
            self.assertEqual(chapters[0].toc_title, "Chapter 1")
            self.assertEqual(chapters[0].word_count, 100)

    @patch('src.epub_parser.epub.read_epub')
    def test_load_error(self, mock_read_epub):
        """Test error handling during load."""
        mock_read_epub.side_effect = Exception("File not found")

        parser = EpubParser("bad.epub")
        with self.assertRaises(Exception):
            parser.load()


if __name__ == "__main__":
    unittest.main()
