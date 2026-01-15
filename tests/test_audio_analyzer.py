import unittest
from unittest.mock import MagicMock, patch, ANY
from src.audio_analyzer import AudioAnalyzer
from src.models import Chapter

class TestAudioAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = AudioAnalyzer("dummy.m4b")

    @patch('src.audio_analyzer.whisper.load_model')
    @patch('src.audio_analyzer.subprocess.run')
    @patch('src.audio_analyzer.os.path.exists')
    @patch('src.audio_analyzer.os.remove')
    def test_find_chapter_linear_success(self, mock_remove, mock_exists, mock_run, mock_load_model):
        """
        Test that linear scan searches chunks and finds a match.
        """
        # Setup Chapter
        chapter = Chapter(index=1, toc_title="Test", search_phrase="Hello World", status="PENDING")
        
        # Mocks
        mock_model = MagicMock()
        mock_load_model.return_value = mock_model
        
        # Mock Transcription Result
        # First chunk: No match
        # Second chunk: Match
        
        # We need the AudioAnalyzer.get_duration to return something valid
        with patch.object(self.analyzer, 'get_duration', return_value=3600.0):
             # Mock transcribe calls
             # We expect it to be called potentially multiple times.
             # Call 1: "Random text"
             # Call 2: "Hello World match"
             
             mock_model.transcribe.side_effect = [
                 {'segments': [{'text': 'Random noise', 'start': 0.0}]},
                 {'segments': [{'text': 'Absolute gibberish', 'start': 0.0}]}, 
                 {'segments': [{'text': 'Hello World is here', 'start': 5.0}]} 
             ]
             
             mock_exists.return_value = True # Temp file exists
             
             # Start search at 100s
             result = self.analyzer.find_chapter_linear(chapter, start_search_time=100.0)
             
             self.assertTrue(result)
             self.assertEqual(chapter.status, "FOUND")
             # Expected time: 
             # Start at 100.
             # Iteration 1: 100. (Returns item 1)
             # Iteration 2: 100 + (240 - 120) = 220. (Returns item 2)
             # Iteration 3: 220 + (240 - 120) = 340. (Returns item 3 - Match at 5.0s)
             # absolute time = 340 + 5.0 = 345.0
             
             self.assertAlmostEqual(chapter.confirmed_time, 345.0)

    @patch('src.audio_analyzer.whisper.load_model')
    @patch('src.audio_analyzer.subprocess.run')
    def test_find_chapter_linear_ffmpeg_fail(self, mock_run, mock_load_model):
        """
        Test resilience against ffmpeg failure.
        """
        chapter = Chapter(index=1, toc_title="Test", search_phrase="Hello", status="PENDING")
        
        import subprocess
        mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg")
        
        with patch.object(self.analyzer, 'get_duration', return_value=3600.0):
            result = self.analyzer.find_chapter_linear(chapter, 0.0)
            self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()
