import pathlib
import unittest
from unittest.mock import mock_open, patch

from src.sync_logic import sync_json_to_md, sync_md_to_json


class TestSyncLogic(unittest.TestCase):

    @patch("json.dump")
    @patch("builtins.open", new_callable=mock_open)
    @patch("pathlib.Path.exists")
    def test_sync_md_to_json(self, mock_exists, mock_file, mock_json_dump):
        # Test MD -> JSON sync logic
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
        self.assertEqual(data[0]['seconds'], 60)  # Recalculated from 00:01:00

        self.assertEqual(data[1]['title'], "Chapter 2")
        self.assertEqual(data[1]['seconds'], 150)  # 2*60 + 30 = 150

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
            "| Chapter | Start Time | Seconds |\n"  # loop stops here
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
