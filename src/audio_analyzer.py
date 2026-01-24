import os
import subprocess
import whisper
import platform
import sys
from thefuzz import fuzz
from .models import Chapter
from .utils import get_logger, seconds_to_hms

logger = get_logger(__name__)

# Try to import mlx_whisper if on Apple Silicon
HAS_MLX = False
if platform.system() == "Darwin" and platform.machine() == "arm64":
    try:
        import mlx_whisper
        HAS_MLX = True
        logger.info("MLX-Whisper detected. Using hardware acceleration 🚀")
    except ImportError:
        logger.info("Apple Silicon detected but mlx-whisper not installed. Using standard CPU.")

class AudioAnalyzer:
    def __init__(self, audio_path: str, model_size="medium"):
        self.audio_path = audio_path
        self.model_size = model_size
        self._model = None
        self.use_mlx = HAS_MLX
        
        # Setup local models directory
        self.models_dir = os.path.join(os.getcwd(), "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        self._ensure_model_available()

    def _ensure_model_available(self):
        """Ensures the appropriate model is downloaded to the local models directory."""
        if self.use_mlx:
            from huggingface_hub import snapshot_download
            
            repo_id = f"mlx-community/whisper-{self.model_size}-mlx"
            local_model_dir = os.path.join(self.models_dir, "mlx-community", f"whisper-{self.model_size}-mlx")
            
            if not os.path.exists(local_model_dir):
                logger.info(f"Downloading MLX model '{repo_id}' to {local_model_dir}...")
                try:
                    snapshot_download(repo_id=repo_id, local_dir=local_model_dir)
                    logger.info("MLX model download complete.")
                except Exception as e:
                    logger.error(f"Failed to download MLX model: {e}")
                    # You might want to fallback to CPU or raise error here
            else:
                logger.info(f"Using cached MLX model from {local_model_dir}")
                
            self.model_path = local_model_dir
        else:
            # Standard Whisper
            # whisper.load_model will use the download_root if specified
            self.download_root = os.path.join(self.models_dir, "openai")
            os.makedirs(self.download_root, exist_ok=True)
            logger.info(f"Standard Whisper model will be cached in {self.download_root}")

    @property
    def model(self):
        """Lazy load the Whisper model (only for standard backend)."""
        if self._model is None and not self.use_mlx:
            logger.info(f"Loading Whisper model ('{self.model_size}')...")
            # This triggers download if not in download_root
            self._model = whisper.load_model(self.model_size, download_root=self.download_root)
        return self._model

    def find_chapter_linear(self, chapter: Chapter, start_search_time: float, max_search_duration=2700, min_confidence=90) -> bool:
        """
        Scans forward from start_search_time in chunks to find the chapter.
        Returns True if found, False if end of file reached or max search exceeded.
        """
        chunk_duration = 240 # 4 minutes
        overlap = 120        # 2 minutes
        
        current_time = start_search_time
        total_duration = self.get_duration()
        
        search_limit = min(total_duration, start_search_time + max_search_duration)
        
        logger.info(f"Scanning Chapter {chapter.index} starting at {seconds_to_hms(int(current_time))}...")
        # logger.info(f"Searching for: {chapter.search_phrase}")
        
        temp_file = "temp_scan.wav"
        chunk_count = 0
        while current_time < search_limit:
            # Define chunk
            chunk_count += 1
            end_time = min(current_time + chunk_duration, total_duration)
            actual_duration = end_time - current_time
            
            if actual_duration < 2:
                break

            # Extract Chunk
            logger.info(
                f"Scanning chunk {chunk_count}: {seconds_to_hms(int(current_time))} - {seconds_to_hms(int(end_time))}..."
            )
            
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(current_time),
                "-t", str(actual_duration),
                "-i", self.audio_path,
                "-ar", "16000",
                "-ac", "1",
                "-loglevel", "error",
                temp_file
            ]
            
            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError:
                logger.error("FFmpeg extraction failed.")
                return False

            # Transcribe
            result = None
            if self.use_mlx:
                # Map model size to mlx-community repo if needed, or let it auto-resolve standard names
                # mlx_whisper usually handles standard names by mapping to default mlx conversions
                try:
                    # no_speech_threshold arg is supported in mlx_whisper.transcribe generally
                    result = mlx_whisper.transcribe(
                        temp_file, 
                        path_or_hf_repo=self.model_path,
                        no_speech_threshold=0.6,
                        language="en"
                    )
                except Exception as e:
                    logger.error(f"MLX Transcription failed: {e}. Falling back to standard.")
                    self.use_mlx = False
                    # IMPORTANT: If we fallback, we need to setup standard model caching
                    self.download_root = os.path.join(self.models_dir, "openai")
                    os.makedirs(self.download_root, exist_ok=True)
            
            if not self.use_mlx:
                model = self.model
                result = model.transcribe(temp_file, language="en", no_speech_threshold=0.6)
            
            best_ratio = 0
            best_segment_time = None
            search_phrase = chapter.search_phrase.lower()
            
            # Fuzzy Match in this chunk
            segments = result.get('segments', []) if isinstance(result, dict) else result
            # Ensure compatibility: mlx output might behave slightly differently but usually returns dict
            
            for segment in segments:
                text = segment['text'].lower().strip()
                if not text:
                    continue

                # SCORING STRATEGY: Start-Bias Weighted Score
                # 1. Partial Ratio: How well 'text' matches *anywhere* in 'search_phrase'.
                #    (High for both "Chapter 1" and "Tally")
                p_ratio = fuzz.partial_ratio(search_phrase, text)
                
                # 2. Start Ratio: How well 'text' matches the *start* of 'search_phrase'.
                #    (High for "Chapter 1", Low for "Tally")
                #    We compare 'text' against the prefix of 'search_phrase' of the same length.
                prefix_len = len(text)
                target_prefix = search_phrase[:prefix_len]
                s_ratio = fuzz.ratio(target_prefix, text)
                
                # Combine: 70% Partial (Robustness) + 30% Start (Positioning)
                # This penalizes matches deep in the paragraph without strictly rejecting 
                # slight mismatches at the start.
                final_score = (0.7 * p_ratio) + (0.3 * s_ratio)
                
                if final_score > best_ratio:
                    best_ratio = final_score
                    best_segment_time = current_time + segment['start']
                
                if p_ratio > 80:
                     logger.debug(f"Candidate: '{text[:20]}...' | Partial: {p_ratio} | Start: {s_ratio} | Final: {int(final_score)}")
                    
                if final_score > 60:
                     logger.debug(f"Match {int(final_score)}% at {int(current_time + segment['start'])}s: {text[:30]}...")

            # Check if found
            if best_ratio >= min_confidence:
                chapter.confirmed_time = best_segment_time
                chapter.status = "FOUND"
                logger.info(f"CONFIRMED Chapter {chapter.index} at {seconds_to_hms(int(best_segment_time))} (Score: {best_ratio:.2f})")
                
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                return True
            
            # Move forward
            # Overlap ensures we don't cut a sentence in half
            current_time += (chunk_duration - overlap)
            
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)
            
        logger.warning(f"FAILED Chapter {chapter.index} - Not found after scanning {(current_time - start_search_time)/60:.1f} min.")
        chapter.status = "FAILED"
        return False

    def get_duration(self) -> float:
        """Returns total duration of audio file in seconds using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error", 
            "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            self.audio_path
        ]
        try:
            output = subprocess.check_output(cmd).decode().strip()
            return float(output)
        except Exception as e:
            logger.error(f"Failed to get duration: {e}")
            return 0.0
