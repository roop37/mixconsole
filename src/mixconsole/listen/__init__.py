"""Offline listening kit: blind A/B + MUSHRA-lite page, local JSON votes, win rates with CIs."""

from mixconsole.listen.kit import build_kit, synthetic_input
from mixconsole.listen.stats import analyze_votes, render_markdown

__all__ = ["analyze_votes", "build_kit", "render_markdown", "synthetic_input"]
