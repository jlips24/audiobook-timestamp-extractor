import unittest
from unittest.mock import MagicMock, patch, call, mock_open
import pathlib
import sys
import json
from src.find_missing import find_missing_chapters, interactive_find_setup
from src.models import Chapter

class TestFindMissing(unittest.TestCase):
    
    def setUp(self):
        self.epub_parser = MagicMock()
        self.mock_chapters = [
            Chapter(index=0, toc_title="Intro", search_phrase="Intro text", status="PENDING"),
            Chapter(index=1, toc_title="Chapter 1", search_phrase="Chap 1 text", status="PENDING"),
            Chapter(index=2, toc_title="Chapter 2", search_phrase="Chap 2 text", status="PENDING"),
            Chapter(index=3, toc_title="Chapter 3", search_phrase="Chap 3 text", status="PENDING"),
            Chapter(index=4, toc_title="Outro", search_phrase="Outro text", status="PENDING"),
        ]
        self.epub_parser.parse.return_value = self.mock_chapters

    @patch("src.find_missing.get_output_dir")
    @patch("src.find_missing.AudioAnalyzer")
    @patch("src.find_missing.json.dump") # Mock json dump directly
    @patch("src.find_missing.open", new_callable=mock_open) # Mock file open
    @patch("src.find_missing.load_existing_timestamps")
    @patch("pathlib.Path.exists")
    def test_find_missing_basic_gap(self, mock_exists, mock_load_json, mock_file, mock_json_dump, mock_analyzer_cls, mock_get_output_dir):
        # Setup Mocks
        mock_exists.return_value = True
        
        # Mock Output Directory
        mock_dir = MagicMock()
        mock_get_output_dir.return_value = mock_dir
        (mock_dir / "chapter_timestamps.json").exists.return_value = True
        
        # Mock Existing Data (JSON List)
        # Chap 1 is found at 100s
        # Chap 2 is MISSING
        # Chap 3 is found at 500s
        mock_load_json.return_value = [
            {"title": "Chapter 1", "seconds": 100},
            {"title": "Chapter 2", "seconds": ""}, # Missing
            {"title": "Chapter 3", "seconds": 500}
        ]
        
        # Mock Analyzer
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.get_duration.return_value = 1000.0
        
        # When finding Chapter 2 (missing), return success at 300s
        def find_side_effect(chapter, start_search_time, max_search_duration):
            if chapter.toc_title == "Chapter 2":
                chapter.status = "FOUND"
                chapter.confirmed_time = 300.0
                return True
            return False
            
        mock_analyzer.find_chapter_linear.side_effect = find_side_effect
 
        # Run
        find_missing_chapters(self.epub_parser, "dummy.m4b", "Author", "Title", "ID")
 
        # Verify
        # We expect a search for Chapter 2.
        # Start: 100 (Chap 1). End: 500 (Chap 3). Window: 400.
        
        calls = mock_analyzer.find_chapter_linear.call_args_list
        found_chap_2_call = False
        for call in calls:
            args, kwargs = call
            chap = args[0]
            start = kwargs.get('start_search_time')
            duration = kwargs.get('max_search_duration')
            
            if chap.toc_title == "Chapter 2":
                found_chap_2_call = True
                # Start should be approx 100 + buffer (5s) => 105
                self.assertTrue(100 <= start <= 110, f"Start time {start} not near 100")
                # Window should be approx 500 - 105 => 395
                self.assertTrue(390 <= duration <= 400, f"Duration {duration} not near 400")
                
        self.assertTrue(found_chap_2_call, "Did not search for Chapter 2")
        
        # Verify Save was called (json.dump)
        mock_json_dump.assert_called_once()
        args, _ = mock_json_dump.call_args
        saved_data = args[0]
        # Verify Chapter 2 is updated in the saved data
        self.assertEqual(saved_data[1]['title'], "Chapter 2")
        self.assertEqual(saved_data[1]['seconds'], 300)

    @patch("src.find_missing.get_output_dir")
    @patch("src.find_missing.AudioAnalyzer")
    @patch("src.find_missing.json.dump")
    @patch("src.find_missing.open", new_callable=mock_open)
    @patch("src.find_missing.load_existing_timestamps")
    @patch("pathlib.Path.exists")
    def test_find_missing_chained_discovery(self, mock_exists, mock_load_json, mock_file, mock_json_dump, mock_analyzer_cls, mock_get_output_dir):
        # Scenario: Chap 1 (100s) ... Chap 2 (Missing) ... Chap 3 (Missing) ... Chap 4 (500s)
        # Note: In the new logic, we iterate the list ONCE.
        # If Chap 2 is found, updates are made IN PLACE in the list.
        # When loop reaches Chap 3, it looks back at "previous found".
        # Does the loop see the *updated* Chap 2? Yes, because we update `existing_data` list objects in place.
        
        mock_exists.return_value = True
        mock_dir = MagicMock()
        mock_get_output_dir.return_value = mock_dir
        (mock_dir / "chapter_timestamps.json").exists.return_value = True
        
        mock_load_json.return_value = [
            {"title": "Chapter 1", "seconds": 100},
            {"title": "Chapter 2", "seconds": ""}, # Missing
            {"title": "Chapter 3", "seconds": ""}, # Missing
            {"title": "Chapter 4", "seconds": 500}
        ]
        
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.get_duration.return_value = 1000.0
        
        def find_side_effect(chapter, start_search_time, max_search_duration):
            if chapter.toc_title == "Chapter 2":
                chapter.confirmed_time = 200.0
                return True
            if chapter.toc_title == "Chapter 3":
                chapter.confirmed_time = 300.0
                return True
            return False
            
        mock_analyzer.find_chapter_linear.side_effect = find_side_effect
        
        find_missing_chapters(self.epub_parser, "dummy.m4b", "Author", "Title", "ID")
        
        # Verify call logic for Chapter 3
        # Should start after Chapter 2 (which was found at 200)
        found_chap_3_call = False
        for call in mock_analyzer.find_chapter_linear.call_args_list:
            args, kwargs = call
            chap = args[0]
            start = kwargs.get('start_search_time')
            
            if chap.toc_title == "Chapter 3":
                found_chap_3_call = True
                # Should start around 200 + buffer
                self.assertTrue(200 <= start <= 210, f"Chapter 3 start {start} should follow Chap 2 (200)")
        
        self.assertTrue(found_chap_3_call)

    @patch("src.find_missing.interactive_find_project_dir")
    @patch("src.find_missing.parse_project_dir")
    @patch("pathlib.Path.exists")
    @patch("src.find_missing.find_missing_chapters")
    @patch("sys.exit")
    def test_interactive_find_setup_success(self, mock_exit, mock_find, mock_exists, mock_parse, mock_interactive):
        # Setup
        mock_project_dir = MagicMock()
        mock_interactive.return_value = mock_project_dir
        
        mock_parse.return_value = ("Author", "Title", "ID")
        
        # Files exist
        (mock_project_dir / "chapter_timestamps.json").exists.return_value = True
        
        # Run
        interactive_find_setup(self.epub_parser, "audio.m4b")
        
        # Verify
        mock_find.assert_called_with(self.epub_parser, "audio.m4b", "Author", "Title", "ID")
        mock_exit.assert_not_called()

    @patch("src.find_missing.interactive_find_project_dir")
    @patch("sys.exit")
    def test_interactive_find_setup_cancel(self, mock_exit, mock_interactive):
        # User cancels at project selection
        mock_interactive.return_value = None
        
        # Configure sys.exit to raise SystemExit so we don't continue execution in the function
        mock_exit.side_effect = SystemExit
        
        with self.assertRaises(SystemExit):
            interactive_find_setup(self.epub_parser, "audio.m4b")
        
        mock_exit.assert_called_with(1)

    @patch("src.find_missing.get_output_dir")
    @patch("src.find_missing.AudioAnalyzer")
    @patch("src.find_missing.save_results")
    @patch("src.find_missing.load_existing_timestamps")
    @patch("pathlib.Path.exists")
    def test_find_missing_no_gaps(self, mock_exists, mock_load_json, mock_save, mock_analyzer_cls, mock_get_output_dir):
        # Scenario: All chapters are already FOUND in JSON.
        mock_exists.return_value = True
        mock_dir = MagicMock()
        mock_get_output_dir.return_value = mock_dir
        (mock_dir / "chapter_timestamps.json").exists.return_value = True
        
        # Mark all as found in JSON (list format)
        mock_load_json.return_value = [
            {"title": "Intro", "seconds": 0.0},
            {"title": "Chapter 1", "seconds": 100.0},
            {"title": "Chapter 2", "seconds": 200.0},
            {"title": "Chapter 3", "seconds": 300.0},
            {"title": "Outro", "seconds": 400.0}
        ]
        
        mock_analyzer = mock_analyzer_cls.return_value
        # Should not need find_chapter calls
        
        find_missing_chapters(self.epub_parser, "dummy.m4b", "Author", "Title", "ID")
        
        # Verify no search calls
        mock_analyzer.find_chapter_linear.assert_not_called()
        
        # Verify save NOT called (no updates made)
        mock_save.assert_not_called()

if __name__ == '__main__':
    unittest.main()
