import unittest
from unittest.mock import MagicMock, patch
from src.epub_parser import EpubParser
from src.models import Chapter
from bs4 import BeautifulSoup

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
        html = "<html><body><h1>Chapter 1</h1><p>First paragraph is now definitely long enough to pass the fifty character threshold without combining.</p><p>Second paragraph is also long enough.</p></body></html>"
        soup = BeautifulSoup(html, 'html.parser')
        
        # We need to access the private method for testing, or expose it.
        # Accessing protected method for unit testing is acceptable in Python.
        parser = EpubParser("dummy.epub")
        primary, secondary = parser._extract_search_phrases(soup)
        
        self.assertEqual(primary, "First paragraph is now definitely long enough to pass the fifty character threshold without combining.")
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
        p1 = "Short but valid paragraph." # 26 chars
        p2 = "This is the second paragraph that is longer."
        
        html = f"<html><body><p>{p1}</p><p>{p2}</p></body></html>"
        soup = BeautifulSoup(html, 'html.parser')
        
        primary, secondary = parser._extract_search_phrases(soup)
        
        self.assertEqual(primary, f"{p1} {p2}"[:150])

if __name__ == "__main__":
    unittest.main()
