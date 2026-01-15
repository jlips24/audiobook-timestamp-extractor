import logging
import sys
import warnings

def setup_logging(level=logging.INFO):
    """Configures the root logger with a standard format."""
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s - %(name)s - %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Suppress Whisper FP16 warning on CPU
    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

def get_logger(name: str):
    return logging.getLogger(name)
