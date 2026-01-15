import unittest
from src.models import Chapter

class TestChapter(unittest.TestCase):
    def test_chapter_initialization(self):
        chap = Chapter(
            index=1,
            toc_title="Prologue",
            search_phrase="Once upon a time",
            status="PENDING"
        )
        self.assertEqual(chap.index, 1)
        self.assertEqual(chap.toc_title, "Prologue")
        self.assertEqual(chap.status, "PENDING")
        self.assertIsNone(chap.confirmed_time)

    def test_chapter_repr(self):
        chap = Chapter(
            index=5,
            toc_title="Chapter 5",
            search_phrase="Hello",
            status="FOUND",
            confirmed_time=120.5
        )
        self.assertIn("Chapter 5", str(chap))
        self.assertIn("Status=FOUND", str(chap))
        self.assertIn("Time=120.5", str(chap))

if __name__ == "__main__":
    unittest.main()
