# Audiobook Timestamp Extractor

Automated tool to extract chapter start times from audiobooks by correlating them with EPUB text.
Designed specifically for complex productions (like "Graphic Audio") where music and sound effects make traditional silence detection unreliable.

## Features
- **Adaptive Estimation**: dynamically adjusts search velocity based on confirmed chapter times to handle uneven reading speeds.
- **Memory Safe**: Uses `ffmpeg` to process audio in small windows, avoiding high RAM usage for large (10hr+) files.
- **Robust Matching**: Combines short paragraphs for unique search phrases and uses fuzzy string matching to handle transcription errors.
- **Interactive Verification**: Allows users to preview and exclude non-narrative sections (Maps, Indexes, etc.) before processing.
- **Whisper Integration**: Leverages OpenAI's Whisper model for accurate speech-to-text even in noisy audio environments.

## Prerequisites
- Python 3.10+
- `ffmpeg` (must be installed and on your system PATH)

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd audiobook-timestamp-extractor
   ```

2. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the tool by providing the paths to your EPUB and Audio file:

```bash
python3 -m src.main "path/to/book.epub" "path/to/audio.m4b"
```

**Workflow:**
1. **Extraction**: The tool parses the EPUB and extracts potential chapters.
2. **Verification**: You will see a list of candidates. Enter IDs of any chapters to ignore (front matter, end notes, etc.).
3. **Estimation & Analysis**: The tool will iterate through chapters, predicting their location and using Whisper to find the exact start time.
4. **Result**: A `chapter_timestamps.json` file is generated with the results.

## Testing

To run the unit test suite:

```bash
python3 -m unittest discover tests
```


## Docker Usage

You can run the application in a Docker container to ensure all dependencies (like ffmpeg) are handled automatically.

1. **Build the image**:
   ```bash
   docker build -t audiobook-extractor .
   ```

2. **Run the container**:
   ```bash
   docker run -p 8501:8501 audiobook-extractor
   ```

3. Open your browser to `http://localhost:8501`.

## Project Structure
- `src/`: Core logic modules
  - `epub_parser.py`: Extracts text and metadata from EPUBs.
  - `audio_analyzer.py`: Handles ffmpeg slicing and Whisper transcription.
  - `estimator.py`: adaptive velocity and time calculation logic.
  - `models.py`: Shared data structures.
- `tests/`: Unit tests for parser and models.
