import unittest
from unittest.mock import MagicMock, patch, ANY
from src.audio_analyzer import AudioAnalyzer
from src.models import Chapter

class TestAudioAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = AudioAnalyzer("dummy.m4b")
        self.analyzer.use_mlx = False # Force disable MLX for unit tests to ensure mocks are used

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

    def test_start_bias_scoring(self):
        """
        Test that Start-Bias scoring prefers matches at the beginning of the phrase.
        """
        # Search Phrase: "Eight hundred... I never knew the tally"
        phrase = "Eight hundred and thirty-three men. I wish I never knew the tally."
        chapter = Chapter(index=1, toc_title="Test", search_phrase=phrase, status="PENDING")
        self.analyzer.use_mlx = False
        
        with patch.object(self.analyzer, 'get_duration', return_value=3600.0), \
             patch('src.audio_analyzer.whisper.load_model') as mock_load, \
             patch('src.audio_analyzer.subprocess.run'), \
             patch('src.audio_analyzer.os.path.exists', return_value=True), \
             patch('src.audio_analyzer.os.remove'):
             
             mock_model = MagicMock()
             mock_load.return_value = mock_model
             
             # Segment 1: "I never knew the tally" (Middle. Partial=100. Start=Low)
             # Segment 2: "Eight hundred" (Start. Partial=100. Start=100)
             
             mock_model.transcribe.return_value = {
                 'segments': [
                     {'text': 'I never knew the tally', 'start': 10.0},
                     {'text': 'Eight hundred and thirty', 'start': 20.0}
                 ]
             }
             
             found = self.analyzer.find_chapter_linear(chapter, 0.0)
             self.assertTrue(found)
             # Should pick 20.0 because it has a better Final Score
             self.assertEqual(chapter.confirmed_time, 20.0)

    def test_start_bias_resilience(self):
        """
        Test that Start-Bias still accepts slightly imperfect starts (e.g. missing 'The')
        """
        phrase = "The quick brown fox jumps."
        chapter = Chapter(index=1, toc_title="Test", search_phrase=phrase, status="PENDING")
        self.analyzer.use_mlx = False
        
        with patch.object(self.analyzer, 'get_duration', return_value=3600.0), \
             patch('src.audio_analyzer.whisper.load_model') as mock_load, \
             patch('src.audio_analyzer.subprocess.run'), \
             patch('src.audio_analyzer.os.path.exists', return_value=True), \
             patch('src.audio_analyzer.os.remove'):
             
             mock_model = MagicMock()
             mock_load.return_value = mock_model
             
             # "Quick brown fox" (Missing "The"). 
             # Partial = 100. Start = Decent (not 0).
             # Should still be > 90 (or whatever min_confidence is, default 90 might be tight, let's say > 80)
             # 0.7*100 + 0.3*ratio("The quick", "quick bro")
             
             mock_model.transcribe.return_value = {
                 'segments': [{'text': 'Quick brown fox', 'start': 5.0}]
             }
             
             # Using default min_confidence=90 might be risky if start ratio drops too low.
             # Let's see if it passes with 90 or if we need to adjust min_confidence expectation.
             # Actually "Quick brown fox" vs "The quick brown" ratio is ~73.
             # 70 + 22 = 92. Should pass 90.
             
             found = self.analyzer.find_chapter_linear(chapter, 0.0)
             self.assertTrue(found)

if __name__ == "__main__":
    unittest.main()
