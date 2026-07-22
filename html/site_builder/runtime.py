"""Process-local services shared by the HTML build modules."""

from pathlib import Path

from .commands import CommandRunner
from .config import BuildConfig


HTML_DIR = Path(__file__).resolve().parent.parent
CONFIG = BuildConfig.load(HTML_DIR)
RUNNER = CommandRunner()

__all__ = ["CONFIG", "HTML_DIR", "RUNNER"]
