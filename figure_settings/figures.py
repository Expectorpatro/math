"""Fixed figure settings for Python computation notebooks.

This module imports Matplotlib lazily, so inspecting or building the static
site does not require the Python computation environment to be active.
"""

from __future__ import annotations


def configure_matplotlib() -> None:
    """Configure deterministic SVG output for an inline notebook backend."""

    from matplotlib import rcParams
    from matplotlib_inline.backend_inline import (
        InlineBackend,
        set_matplotlib_formats,
    )

    rcParams.update(
        {
            "svg.fonttype": "path",
            "svg.hashsalt": "textbook",
        }
    )
    backend = InlineBackend.instance()
    backend.print_figure_kwargs = {
        "bbox_inches": None,
        "metadata": {"Date": None},
    }
    set_matplotlib_formats("svg", metadata={"Date": None})
    backend.figure_formats = {"svg"}
