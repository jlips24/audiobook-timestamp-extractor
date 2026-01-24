import unittest
from unittest.mock import MagicMock, patch

from src.models import Chapter
from src.user_interaction import get_book_metadata, verify_chapters


class TestUserInteraction(unittest.TestCase):

    @patch('builtins.input', side_effect=[''])  # User presses Enter (no ignore)
    @patch('builtins.print')
    def test_verify_chapters_no_ignore(self, mock_print, mock_input):
        c1 = Chapter(index=1, toc_title="C1", search_phrase="S1", status="PENDING")
        c2 = Chapter(index=2, toc_title="C2", search_phrase="S2", status="PENDING")
        chapters = [c1, c2]

        result = verify_chapters(chapters)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].index, 1)
        self.assertEqual(result[1].index, 2)

    @patch('builtins.input', side_effect=['1'])  # User ignores 1
    @patch('builtins.print')
    def test_verify_chapters_ignore_single(self, mock_print, mock_input):
        c1 = Chapter(index=1, toc_title="C1", search_phrase="S1", status="PENDING")
        c2 = Chapter(index=2, toc_title="C2", search_phrase="S2", status="PENDING")
        chapters = [c1, c2]

        result = verify_chapters(chapters)

        # Should return only c2
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].index, 2)

        # c1 should be marked IGNORED in the original list
        self.assertEqual(c1.status, "IGNORED")

    @patch('builtins.input', side_effect=['2-3'])  # User ignores range 2-3
    @patch('builtins.print')
    def test_verify_chapters_ignore_range(self, mock_print, mock_input):
        c1 = Chapter(index=1, toc_title="C1", search_phrase="S1", status="PENDING")
        c2 = Chapter(index=2, toc_title="C2", search_phrase="S2", status="PENDING")
        c3 = Chapter(index=3, toc_title="C3", search_phrase="S3", status="PENDING")
        chapters = [c1, c2, c3]

        result = verify_chapters(chapters)

        # Should return only c1
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].index, 1)
        self.assertEqual(c2.status, "IGNORED")
        self.assertEqual(c3.status, "IGNORED")

    @patch('builtins.input', side_effect=['invalid', '1'])  # Invalid then valid
    @patch('builtins.print')
    def test_verify_chapters_invalid_retry(self, mock_print, mock_input):
        c1 = Chapter(index=1, toc_title="C1", search_phrase="S1", status="PENDING")
        chapters = [c1]

        # Recursion: verify_chapters calls itself.
        # We need to ensure the mocked side_effect works across recursive calls.
        # It does since input() pulls from the iterator.

        result = verify_chapters(chapters)

        # Finally returns empty list since C1 is ignored
        self.assertEqual(len(result), 0)
        self.assertEqual(c1.status, "IGNORED")

    @patch('builtins.input', side_effect=['My Author', 'My Title', '12345'])
    @patch('builtins.print')
    def test_get_book_metadata_custom(self, mock_print, mock_input):
        mock_parser = MagicMock()
        mock_parser.get_metadata.return_value = {}

        author, title, aid = get_book_metadata(mock_parser)

        self.assertEqual(author, "My Author")
        self.assertEqual(title, "My Title")
        self.assertEqual(aid, "12345")

    @patch('builtins.input', side_effect=['', '', '12345'])
    @patch('builtins.print')
    def test_get_book_metadata_defaults(self, mock_print, mock_input):
        mock_parser = MagicMock()
        mock_parser.get_metadata.return_value = {
            'author': 'Def Auth',
            'title': 'Def Title'
        }

        author, title, aid = get_book_metadata(mock_parser)

        self.assertEqual(author, "Def Auth")
        self.assertEqual(title, "Def Title")
        self.assertEqual(aid, "12345")


if __name__ == "__main__":
    unittest.main()
