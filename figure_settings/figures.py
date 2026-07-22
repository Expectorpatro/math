"""Central high-resolution figure settings for computation notebooks.

This module imports Matplotlib lazily, so inspecting or building the static
site does not require the Python computation environment to be active.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
import tomllib
from typing import Literal


@dataclass(frozen=True, slots=True)
class FigurePolicy:
    """Settings shared by all Python computation figures."""

    preferred_format: Literal["svg", "png"]
    raster_dpi: int
    minimum_raster_width: int


def load_figure_policy() -> FigurePolicy:
    """Read the authoritative image policy from ``html/build-config.toml``."""

    project_root = Path(__file__).resolve().parent.parent
    config_path = project_root / "html" / "build-config.toml"
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    images = raw["images"]
    preferred = str(images["computation_preferred_format"]).lower()
    if preferred not in {"svg", "png"}:
        raise ValueError(
            "computation_preferred_format must be either 'svg' or 'png'"
        )
    return FigurePolicy(
        preferred_format=preferred,  # type: ignore[arg-type]
        raster_dpi=int(images["computation_raster_dpi"]),
        minimum_raster_width=int(images["computation_min_raster_width"]),
    )


def configure_matplotlib() -> FigurePolicy:
    """Configure deterministic vector output for an inline notebook backend.

    SVG is preferred because it remains sharp at every device pixel ratio.  If
    the central policy requests PNG, the inline backend uses a retina image and
    the configured DPI.  Data, axes limits, figure sizes, and plotting calls are
    intentionally untouched.
    """

    policy = load_figure_policy()
    import matplotlib
    from matplotlib_inline.backend_inline import InlineBackend, set_matplotlib_formats

    output_dpi = policy.raster_dpi
    if policy.preferred_format == "png":
        # The inline ``retina`` formatter emits two device pixels per logical
        # pixel.  Raise the base DPI when necessary so a default-width figure
        # reaches the central raster-width target; unusually narrow figures
        # are still caught by the site build's strict image audit.
        default_width_inches = float(matplotlib.rcParams["figure.figsize"][0])
        output_dpi = max(
            output_dpi,
            math.ceil(policy.minimum_raster_width / (2 * default_width_inches)),
        )

    matplotlib.rcParams.update(
        {
            "figure.dpi": output_dpi,
            "savefig.dpi": output_dpi,
            "svg.fonttype": "path",
            "svg.hashsalt": "textbook",
        }
    )
    backend = InlineBackend.instance()
    backend.print_figure_kwargs = {
        "bbox_inches": None,
        "metadata": {"Date": None},
    }
    if policy.preferred_format == "svg":
        set_matplotlib_formats("svg", metadata={"Date": None})
        backend.figure_formats = {"svg"}
    else:
        set_matplotlib_formats("retina")
        backend.figure_formats = {"retina"}
    return policy
