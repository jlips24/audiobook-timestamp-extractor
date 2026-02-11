import logging
import sys
import warnings


def seconds_to_hms(seconds: int) -> str:
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


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


def sanitize(s: str) -> str:
    # Allow alphanumeric, space, dash, underscore, dots, commas, parens
    allowed = set(" -_.,()")
    return "".join(c for c in s if c.isalnum() or c in allowed).strip()
