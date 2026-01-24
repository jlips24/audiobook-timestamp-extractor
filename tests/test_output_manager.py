import unittest
from unittest.mock import MagicMock, patch, mock_open, call
from src.output_manager import save_results
from src.models import Chapter
import json
import pathlib

class TestOutputManager(unittest.TestCase):

    @patch('src.output_manager.subprocess.run')
    @patch('src.output_manager.pathlib.Path.mkdir')
    @patch('src.output_manager.open', new_callable=mock_open)
    @patch('src.output_manager.json.dump')
    def test_save_results_basic(self, mock_json_dump, mock_file, mock_mkdir, mock_subprocess):
        """
        Test that save_results writes correct JSON and Markdown files.
        """
        # Setup Data
        c1 = Chapter(index=1, toc_title="Chapter 1", search_phrase="Start", status="FOUND", confirmed_time=65.0) # 1:05
        c2 = Chapter(index=2, toc_title="Chapter 2", search_phrase="Next", status="FOUND", confirmed_time=125.0) # 2:05
        c3 = Chapter(index=3, toc_title="Ignored", search_phrase="Skip", status="IGNORED") # Should not be in output normally if filtered before, but save_results receives 'valid_chapters'
        
        # NOTE: save_results loop processes all given chapters. If logic says "status == FOUND" it adds time.
        # If not found, it adds empty string.
        
        chapters = [c1, c2, c3]
        
        author = "TestAuthor"
        title = "TestTitle"
        audible_id = "12345"
        
        save_results(chapters, author, title, audible_id)
        
        # Verify Directory Creation
        # repo/TestAuthor/TestTitle [12345]
        expected_path = pathlib.Path("repo") / author / f"{title} [{audible_id}]"
        # Since we mocked mkdir on the Path object instance created inside the function, checking calls is tricky directly on the class.
        # But we can assume it works if no error.
        
        # Verify JSON
        # json.dump called with list of dicts
        self.assertTrue(mock_json_dump.called)
        args, _ = mock_json_dump.call_args
        data = args[0]
        
        # Since c1 starts at 65s (>10s), an Intro chapter is auto-inserted!
        # Expected: [Intro, C1, C2, C3(ignored)] -> 4 items
        self.assertEqual(len(data), 4)
        
        # Check Intro
        self.assertEqual(data[0]['title'], "Intro / Prologue")
        self.assertEqual(data[0]['start_time'], "00:00:00")
        
        # Check C1 (now index 1)
        self.assertEqual(data[1]['title'], "Chapter 1")
        self.assertEqual(data[1]['start_time'], "00:01:05")
        self.assertEqual(data[1]['seconds'], 65)
        
        # Check C3 (Ignored, index 3)
        self.assertEqual(data[3]['title'], "Ignored")
        self.assertEqual(data[3]['start_time'], "")
        
        # Verify Markdown Write
        # Handles are tricky with multiple file opens.
        # mock_file() returns the file handle.
        handle = mock_file()
        
        # Check that we wrote to md file
        # We can inspect the write calls on the handle
        # Just ensure some markdown content is written
        written_content = "".join(call.args[0] for call in handle.write.call_args_list)
        self.assertIn("| Chapter 1 | 00:01:05 | 65 |", written_content)
        self.assertIn("| Chapter 2 | 00:02:05 | 125 |", written_content)
        
    @patch('src.output_manager.subprocess.run')
    @patch('src.output_manager.pathlib.Path.mkdir')
    @patch('src.output_manager.open', new_callable=mock_open)
    @patch('src.output_manager.json.dump')
    def test_save_results_intro_insertion(self, mock_json_dump, mock_file, mock_mkdir, mock_subprocess):
        """
        Test that save_results inserts an Intro chapter if the first chapter starts late.
        """
        # First chapter starts at 20 seconds (> 10s threshold)
        c1 = Chapter(index=1, toc_title="Chapter 1", search_phrase="Start", status="FOUND", confirmed_time=20.0) 
        chapters = [c1]
        
        save_results(chapters, "Auth", "Book", "ID")
        
        # Verify JSON has Intro
        args, _ = mock_json_dump.call_args
        data = args[0]
        
        # Should have 2 items: Intro, Chapter 1
        self.assertEqual(len(data), 2)
        
        self.assertEqual(data[0]['title'], "Intro / Prologue")
        self.assertEqual(data[0]['start_time'], "00:00:00")
        
        self.assertEqual(data[1]['title'], "Chapter 1")
        self.assertEqual(data[1]['start_time'], "00:00:20")
        
if __name__ == "__main__":
    unittest.main()
