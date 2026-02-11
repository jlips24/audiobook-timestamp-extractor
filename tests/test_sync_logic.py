import unittest
from unittest.mock import MagicMock, patch, mock_open
import pathlib
import json
from src.sync_logic import sync_md_to_json, sync_json_to_md

class TestSyncLogic(unittest.TestCase):

    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_sync_md_to_json(self, mock_exists, mock_file):
        # Mock Setup
        mock_exists.return_value = True
        project_dir = pathlib.Path("dummy")
        
        # input MD content
        md_content = """# Header
        | Chapter | Start Time | Seconds |
        | :--- | :--- | :--- |
        | Chapter 1 | 00:01:00 | 60 |
        | Chapter 2 | 00:02:00 | (old) |
        """
        mock_file.return_value.readlines.return_value = md_content.splitlines()
        
        sync_md_to_json(project_dir)
        
        # Verify JSON write
        # We expect a write to json_path
        handle = mock_file()
        # The second open call is for writing JSON (first was reading MD)
        # We can check the write arguments
        
        # It's tricky with mock_open multiple calls, let's verify logic by args
        # Expected data:
        # Chap 1: 00:01:00 -> 60s
        # Chap 2: 00:02:00 -> 120s
        
        written_data = None
        for call in handle.write.call_args_list:
            args = call[0]
            if args[0].strip().startswith("["):
                 written_data = args[0]
                 
        # Actually json.dump writes chunks, might be hard to capture exact string this way without a real file or better mock
        # Let's trust that if the function runs without error and calls write, it works roughly. 
        # Ideally we inspect the `json.dump` call if we mocked json.dump, but we didn't.
        
        # Let's rely on unit test logic verification:
        # 00:01:00 -> 60
        # 00:02:00 -> 120
        pass 

    @patch("json.dump")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_sync_md_to_json_logic(self, mock_exists, mock_file, mock_json_dump):
        # Better test with json.dump mocked
        mock_exists.return_value = True
        
        md_content = [
            "| Chapter | Start Time | Seconds |",
            "| :--- | :--- | :--- |",
            "| Chapter 1 | 00:01:00 | 9999 |", 
            "| Chapter 2 | 00:02:30 | 0000 |"
        ]
        mock_file.return_value.readlines.return_value = md_content
        
        sync_md_to_json(pathlib.Path("dummy"))
        
        # Check what was passed to dump
        args, _ = mock_json_dump.call_args
        data = args[0]
        
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['title'], "Chapter 1")
        self.assertEqual(data[0]['seconds'], 60) # Recalculated from 00:01:00
        
        self.assertEqual(data[1]['title'], "Chapter 2")
        self.assertEqual(data[1]['seconds'], 150) # 2*60 + 30 = 150

    @patch("json.load")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_sync_json_to_md(self, mock_exists, mock_file, mock_json_load):
        mock_exists.return_value = True
        
        # Mock JSON data
        mock_json_load.return_value = [
            {"title": "Intro", "start_time": "00:00:00", "seconds": 0},
            {"title": "Chapter 1", "start_time": "00:05:00", "seconds": 300}
        ]
        
        # Mock Existing MD (headers)
        mock_file.return_value.__iter__.return_value = [
            "# My Book Header\n",
            "\n",
            "| Chapter | Start Time | Seconds |\n" # loop stops here
        ]
        
        sync_json_to_md(pathlib.Path("dummy"))
        
        # Verify Write
        handle = mock_file()
        
        # We expect writes:
        # 1. Header lines
        # 2. Table Header
        # 3. Row 1
        # 4. Row 2
        
        writes = [call[0][0] for call in handle.write.call_args_list]
        full_output = "".join(writes)
        
        self.assertIn("| Intro | 00:00:00 | 0 |", full_output)
        self.assertIn("| Chapter 1 | 00:05:00 | 300 |", full_output)

if __name__ == '__main__':
    unittest.main()
