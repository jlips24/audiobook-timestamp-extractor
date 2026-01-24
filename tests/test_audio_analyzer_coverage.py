import unittest
from unittest.mock import MagicMock, patch
from src.audio_analyzer import AudioAnalyzer
import sys

class TestAudioAnalyzerInitialization(unittest.TestCase):
    """
    Tests specific to initialization, model downloading, and MLX paths.
    """

    @patch('src.audio_analyzer.os.makedirs')
    @patch('src.audio_analyzer.whisper.load_model') 
    def test_ensure_model_available_standard(self, mock_load, mock_makedirs):
        # Test Standard Whisper Path: HAS_MLX=False
        
        with patch('src.audio_analyzer.HAS_MLX', False):
            # We don't patch _ensure_model_available, so it runs real logic.
            # It will create 'models/openai' and set download_root.
            analyzer = AudioAnalyzer("dummy.m4b", model_size="tiny")
            
            # Check if download_root was set correctly
            self.assertTrue(hasattr(analyzer, 'download_root'))
            self.assertTrue(analyzer.download_root.endswith("models/openai"))
            
            # Check that models dir was created
            mock_makedirs.assert_called()

    def test_ensure_model_available_mlx_download(self):
        """
        Test MLX Path (HAS_MLX=True).
        Verifies that snapshot_download is called when model doesn't exist.
        """
        # We need to mock 'huggingface_hub' which is imported *inside* the function.
        mock_hf_hub = MagicMock()
        mock_snapshot = MagicMock()
        mock_hf_hub.snapshot_download = mock_snapshot
        
        with patch('src.audio_analyzer.HAS_MLX', True), \
             patch('src.audio_analyzer.os.makedirs'), \
             patch('src.audio_analyzer.os.path.exists', return_value=False), \
             patch.dict(sys.modules, {'huggingface_hub': mock_hf_hub}):
             
             analyzer = AudioAnalyzer("dummy.m4b", model_size="large")
             
             # Verify snapshot_download called
             mock_snapshot.assert_called()
             # Verify args
             call_args = mock_snapshot.call_args
             self.assertEqual(call_args[1]['repo_id'], "mlx-community/whisper-large-mlx")

    @patch('src.audio_analyzer.os.makedirs')
    @patch('src.audio_analyzer.os.path.exists', return_value=False)
    def test_ensure_model_available_mlx_download_fail(self, mock_exists, mock_makedirs):
        # Test MLX Download Failure
        mock_hf_hub = MagicMock()
        mock_hf_hub.snapshot_download.side_effect = Exception("Network Error")
        
        with patch('src.audio_analyzer.HAS_MLX', True), \
             patch.dict(sys.modules, {'huggingface_hub': mock_hf_hub}):
             
             with self.assertLogs('src.audio_analyzer', level='ERROR') as cm:
                 analyzer = AudioAnalyzer("dummy.m4b", model_size="tiny")
                 self.assertTrue(any("Failed to download MLX model" in o for o in cm.output))

    def test_get_duration_success(self):
        with patch('src.audio_analyzer.AudioAnalyzer._ensure_model_available'), \
             patch('src.audio_analyzer.os.makedirs'), \
             patch('src.audio_analyzer.subprocess.check_output', return_value=b"123.45\n"):
             
            analyzer = AudioAnalyzer("dummy.m4b")
            duration = analyzer.get_duration()
            self.assertEqual(duration, 123.45)

    def test_get_duration_fail(self):
        with patch('src.audio_analyzer.AudioAnalyzer._ensure_model_available'), \
             patch('src.audio_analyzer.os.makedirs'), \
             patch('src.audio_analyzer.subprocess.check_output', side_effect=Exception("Error")):
             
            analyzer = AudioAnalyzer("dummy.m4b")
            duration = analyzer.get_duration()
            self.assertEqual(duration, 0.0)

if __name__ == "__main__":
    unittest.main()
