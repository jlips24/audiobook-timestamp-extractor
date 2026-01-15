import os
import subprocess
import whisper
from thefuzz import fuzz
from .models import Chapter
from .utils import get_logger

logger = get_logger(__name__)

class AudioAnalyzer:
    def __init__(self, audio_path: str, model_size="base"):
        self.audio_path = audio_path
        self.model_size = model_size
        self._model = None

    @property
    def model(self):
        """Lazy load the Whisper model."""
        if self._model is None:
            logger.info(f"Loading Whisper model ('{self.model_size}')...")
            self._model = whisper.load_model(self.model_size)
        return self._model

    def find_chapter_linear(self, chapter: Chapter, start_search_time: float, max_search_duration=1800, min_confidence=80) -> bool:
        """
        Scans forward from start_search_time in chunks to find the chapter.
        Returns True if found, False if end of file reached or max search exceeded.
        """
        chunk_duration = 240 # 4 minutes
        overlap = 120        # 2 minutes
        
        current_time = start_search_time
        total_duration = self.get_duration()
        
        search_limit = min(total_duration, start_search_time + max_search_duration)
        
        logger.info(f"Scanning Chapter {chapter.index} starting at {int(current_time)}s...")
        
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
            logger.info(f"Scanning chunk {chunk_count}: {int(current_time)}s - {int(end_time)}...")
            
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
            model = self.model
            result = model.transcribe(temp_file, language="en", no_speech_threshold=0.6)
            
            best_ratio = 0
            best_segment_time = None
            search_phrase = chapter.search_phrase.lower()
            
            # Fuzzy Match in this chunk
            for segment in result['segments']:
                text = segment['text'].lower()
                ratio = fuzz.partial_ratio(search_phrase, text)
                
                if ratio > best_ratio:
                    best_ratio = ratio
                    # Absolute time = Chunk Start + Segment Start
                    best_segment_time = current_time + segment['start']
                    
                if ratio > 60:
                     logger.debug(f"Match {ratio}% at {int(current_time + segment['start'])}s: {text[:30]}...")

            # Check if found
            if best_ratio >= min_confidence:
                chapter.confirmed_time = best_segment_time
                chapter.status = "FOUND"
                logger.info(f"CONFIRMED Chapter {chapter.index} at {best_segment_time:.2f}s (Score: {best_ratio})")
                
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
