"""Maintainable HTML build system for the textbook.

The public entry point remains :mod:`html.build`; this package contains the
independent configuration, rendering, resource, validation, and publishing
services used by that compatibility entry point.
"""

from .config import BuildConfig, BuildPaths, ImageQuality
from .errors import BuildError

__all__ = ["BuildConfig", "BuildError", "BuildPaths", "ImageQuality"]
