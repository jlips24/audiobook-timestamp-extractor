import unittest
from unittest.mock import MagicMock, patch, mock_open
import pathlib
from src.find_missing import find_missing_chapters
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
    @patch("src.find_missing.save_results")
    @patch("src.find_missing.load_existing_timestamps")
    @patch("pathlib.Path.exists")
    def test_find_missing_basic_gap(self, mock_exists, mock_load_json, mock_save, mock_analyzer_cls, mock_get_output_dir):
        # Setup Mocks
        mock_exists.return_value = True
        
        # Mock Output Directory
        mock_dir = MagicMock()
        mock_get_output_dir.return_value = mock_dir
        (mock_dir / "chapter_timestamps.json").exists.return_value = True
        
        # Mock Existing Data (JSON)
        # Chap 1 is found at 100s
        # Chap 3 is found at 500s
        # Chap 2 is MISSING
        mock_load_json.return_value = {
            "Chapter 1": 100.0,
            "Chapter 3": 500.0
        }
        
        # Mock Analyzer
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.get_duration.return_value = 1000.0
        
        # When finding Chapter 2 (missing), return success at 300s
        def find_side_effect(chapter, start_search_time, max_search_duration):
            if chapter.index == 2:
                chapter.status = "FOUND"
                chapter.confirmed_time = 300.0
                return True
            return False
            
        mock_analyzer.find_chapter_linear.side_effect = find_side_effect

        # Run
        find_missing_chapters(self.epub_parser, "dummy.m4b", "Author", "Title", "ID")

        # Verified loaded state
        # Chap 0 (Intro) should be PENDING (not in JSON)
        # Chap 1 should be FOUND 100.0
        # Chap 3 should be FOUND 500.0
        self.assertEqual(self.mock_chapters[1].status, "FOUND")
        self.assertEqual(self.mock_chapters[1].confirmed_time, 100.0)
        
        # Verify calls
        # We expect a search for Intro (Index 0). 
        #   Start: 0 (no prev). End: 100 (Chap 1). Window: 100.
        # We expect a search for Chapter 2 (Index 2). 
        #   Start: 100 (Chap 1). End: 500 (Chap 3). Window: 400.
        # We expect a search for Outro (Index 4). 
        #   Start: 500 (Chap 3). End: 1000 (Duration). Window: 500.
        
        calls = mock_analyzer.find_chapter_linear.call_args_list
        
        # Check Chapter 2 specific call
        found_chap_2_call = False
        for call in calls:
            args, kwargs = call
            chap = args[0]
            start = kwargs.get('start_search_time')
            duration = kwargs.get('max_search_duration')
            
            if chap.index == 2:
                found_chap_2_call = True
                # Start should be approx 100 + buffer (5s) => 105
                self.assertTrue(100 <= start <= 110, f"Start time {start} not near 100")
                # Window should be approx 500 - 105 => 395
                self.assertTrue(390 <= duration <= 400, f"Duration {duration} not near 400")
                
        self.assertTrue(found_chap_2_call, "Did not search for Chapter 2")
        
        # Verify Save was called
        mock_save.assert_called_once()
        
    @patch("src.find_missing.get_output_dir")
    @patch("src.find_missing.AudioAnalyzer")
    @patch("src.find_missing.save_results")
    @patch("src.find_missing.load_existing_timestamps")
    @patch("pathlib.Path.exists")
    def test_find_missing_chained_discovery(self, mock_exists, mock_load_json, mock_save, mock_analyzer_cls, mock_get_output_dir):
        # Scenario: Chap 1 (100s) ... Chap 2 (Missing) ... Chap 3 (Missing) ... Chap 4 (500s)
        # If Chap 2 is found, Chap 3 search should start from Chap 2's new time.
        
        mock_exists.return_value = True
        mock_dir = MagicMock()
        mock_get_output_dir.return_value = mock_dir
        (mock_dir / "chapter_timestamps.json").exists.return_value = True
        
        mock_load_json.return_value = {
            "Chapter 1": 100.0,
            "Outro": 500.0 # Using Outro as the anchor at 500
        }
        
        mock_analyzer = mock_analyzer_cls.return_value
        mock_analyzer.get_duration.return_value = 1000.0
        
        def find_side_effect(chapter, start_search_time, max_search_duration):
            if chapter.index == 2: # Found Chap 2
                chapter.status = "FOUND"
                chapter.confirmed_time = 200.0
                return True
            if chapter.index == 3: # Found Chap 3
                chapter.status = "FOUND"
                chapter.confirmed_time = 300.0
                return True
            return False
            
        mock_analyzer.find_chapter_linear.side_effect = find_side_effect
        
        find_missing_chapters(self.epub_parser, "dummy.m4b", "Author", "Title", "ID")
        
        # Check call logic for Chapter 3
        # Should start after Chapter 2 (which was found at 200)
        found_chap_3_call = False
        for call in mock_analyzer.find_chapter_linear.call_args_list:
            args, kwargs = call
            chap = args[0]
            start = kwargs.get('start_search_time')
            
            if chap.index == 3:
                found_chap_3_call = True
                # Should start around 200 + buffer
                self.assertTrue(200 <= start <= 210, f"Chapter 3 start {start} should follow Chap 2 (200)")
        
        self.assertTrue(found_chap_3_call)

if __name__ == '__main__':
    unittest.main()
