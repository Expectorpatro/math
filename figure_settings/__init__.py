"""Shared rendering policy for executable textbook computations."""

from .figures import FigurePolicy, configure_matplotlib, load_figure_policy

__all__ = ["FigurePolicy", "configure_matplotlib", "load_figure_policy"]
