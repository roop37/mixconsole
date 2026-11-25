# ruff: noqa: E501
"""Offline HTML report: local audio, inline waveform/automation SVG and explanations."""

import html
import os
from pathlib import Path
from urllib.parse import quote

import numpy as np

from mixconsole.analysis.models import TrackAnalysis
from mixconsole.mixscript.models import AutomationLane, MixScript


def _line(seconds: float, duration: float, color: str, opacity: float, width: float = 1) -> str:
    x = 800 * seconds / duration
    return (
        f'<line x1="{x:.2f}" x2="{x:.2f}" y1="0" y2="100" '
        f'stroke="{color}" stroke-opacity="{opacity}" stroke-width="{width}"/>'
    )


def _waveform(analysis: TrackAnalysis, cue: float | None = None) -> str:
    values = analysis.arrays.get("bar_energy")
    if values is None or len(values) == 0:
        values = np.ones((1, 1))
    power = np.sqrt(np.maximum(np.asarray(values)[:, 0], 0))
    power /= max(float(np.max(power)), 1e-9)
    width = 800 / len(power)
    waveform = "".join(
        f'<rect x="{i * width:.2f}" y="{50 - p * 45:.2f}" '
        f'width="{max(1, width - 1):.2f}" height="{2 * p * 45:.2f}"/>'
        for i, p in enumerate(power)
    )
    beats = "".join(_line(t, analysis.duration, "#7c8a9f", 0.18) for t in analysis.beats)
    bars = "".join(_line(bar.start, analysis.duration, "#abc6df", 0.45) for bar in analysis.bars)
    phrases = "".join(
        _line(phrase.start, analysis.duration, "#efad36", 0.9, 1.5) for phrase in analysis.phrases
    )
    sections = "".join(
        _line(section.start, analysis.duration, "#ba78e0", 0.8, 2) for section in analysis.sections
    )
    chosen = _line(cue, analysis.duration, "#f35d59", 1, 3) if cue is not None else ""
    return (
        '<svg viewBox="0 0 800 100" role="img" '
        'aria-label="Waveform with beat, bar, phrase, section and cue markers">'
        f'<g fill="#5ba5df">{waveform}</g>{beats}{bars}{phrases}{sections}{chosen}</svg>'
    )


def _automation(lanes: list[AutomationLane]) -> str:
    if not lanes:
        return "<p>No automation lanes.</p>"
    last = max(point.beat for lane in lanes for point in lane.points) or 1
    paths: list[str] = []
    for lane in lanes:
        values = [point.value for point in lane.points]
        low, high = min(values), max(values)
        span = max(high - low, 1e-9)
        points = " ".join(
            f"{800 * point.beat / last:.2f},{95 - (point.value - low) / span * 90:.2f}"
            for point in lane.points
        )
        color = "#62b6e8" if lane.target.track == "deck_a" else "#f6b463"
        label = f"{lane.target.track} {lane.parameter}: {low:g} to {high:g}"
        paths.append(
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="3"><title>{html.escape(label)}</title></polyline>'
        )
    return (
        '<svg viewBox="0 0 800 100" role="img" aria-label="Gain automation curves">'
        + "".join(paths)
        + "</svg>"
    )


def render_analysis_html(analysis: TrackAnalysis, audio_path: Path, html_path: Path) -> str:
    """Standalone analysis viewer with local playback and waveform seeking."""
    relative = os.path.relpath(audio_path.resolve(), html_path.resolve().parent)
    source = html.escape(quote(relative, safe="/"), quote=True)
    loudness = analysis.arrays.get("short_term_lufs")
    curve = ""
    if loudness is not None and len(loudness):
        values = np.clip(np.asarray(loudness), -60, 0)
        # At most 800 plotted points, with a stable stride for long tracks.
        stride = max(1, (len(values) + 799) // 800)
        curve = " ".join(
            f"{800 * i * analysis.loudness.hop_seconds / analysis.duration:.2f},"
            f"{95 - (value + 60) * 1.5:.2f}"
            for i, value in enumerate(values)
            if i % stride == 0
        )
    title = html.escape(Path(analysis.file).name)
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>{title} · MixConsole analysis</title><style>body{{font:16px system-ui;max-width:1000px;margin:auto;padding:24px;background:#101723;color:#eee}}svg{{width:100%;background:#1b2637}}#wave{{cursor:pointer}}audio{{width:100%}}</style><h1>{title}</h1><p>{analysis.duration:.1f} s · {analysis.global_bpm or 0:.1f} BPM · {len(analysis.sections)} sections</p><p>Click the waveform to seek. Markers: beat (gray), bar (blue), phrase (amber), section (purple).</p><div id="wave">{_waveform(analysis)}</div><audio id="player" controls preload="metadata" src="{source}"></audio><h2>Short-term loudness (LUFS)</h2><svg viewBox="0 0 800 100" role="img" aria-label="Short-term LUFS from -60 to 0"><polyline points="{curve}" fill="none" stroke="#65d5b4" stroke-width="2"/></svg><script>document.getElementById('wave').addEventListener('click', function(event) {{ const svg = this.querySelector('svg'); const bounds = svg.getBoundingClientRect(); const position = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)); const player = document.getElementById('player'); player.currentTime = position * {analysis.duration:.9f}; }});</script></html>"""


def render_html(
    script: MixScript,
    a: TrackAnalysis,
    b: TrackAnalysis,
    verifications: list[dict[str, object]],
) -> str:
    transition = script.transitions[0]
    features = sorted({key for c in transition.candidates for key in c.score_breakdown})
    header = "".join(f"<th>{html.escape(feature)}</th>" for feature in features)
    rows = "".join(
        f"<tr><td>{html.escape(c.id)}</td><td>{html.escape(c.family)}</td><td>{c.score:.3f}</td>"
        + "".join(f"<td>{c.score_breakdown.get(feature, 0):.3f}</td>" for feature in features)
        + "</tr>"
        for c in transition.candidates
    )
    cards = "".join(
        f"<article><h3>{html.escape(c.family)} · {c.score:.3f}</h3>"
        f"<p>Exit {c.exit.seconds:.2f}s, entry {c.entry.seconds:.2f}s, "
        f"{c.length_bars} bars</p>"
        + (
            f'<audio controls preload="none" src="{html.escape(c.preview_artifact, quote=True)}"></audio>'
            if c.preview_artifact
            else ""
        )
        + "</article>"
        for c in transition.candidates
    )
    rejections = "".join(
        f"<li>{html.escape(item.candidate_id)}: {html.escape(item.reason)}</li>"
        for item in (transition.explanation.rejected_candidates if transition.explanation else [])
    )
    checks = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(value))}</td>"
            for value in (result.get("candidate"), result.get("passed"), result.get("reason"))
        )
        + "</tr>"
        for result in verifications
    )
    explanation = transition.explanation.chosen_because if transition.explanation else ""
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><title>MixConsole transition</title><style>body{{font:16px system-ui;max-width:1000px;margin:auto;padding:24px;background:#101723;color:#eee}}svg{{width:100%;background:#1b2637}}article{{padding:12px;border:1px solid #445;margin:8px 0}}table{{border-collapse:collapse;display:block;overflow-x:auto}}th,td{{border:1px solid #445;padding:5px 12px}}audio{{width:100%}}summary{{cursor:pointer}}</style><h1>{html.escape(Path(a.file).name)} → {html.escape(Path(b.file).name)}</h1><p>Chosen: {html.escape(transition.family)}. {html.escape(explanation)}</p><p>Markers: beat (gray), bar (blue), phrase (amber), section (purple), chosen cue (red).</p><h2>Deck A</h2>{_waveform(a, transition.exit.seconds)}<h2>Deck B</h2>{_waveform(b, transition.entry.seconds)}<h2>Automation</h2>{_automation(transition.automation)}<h2>Audition candidates</h2>{cards}<h2>Score breakdown</h2><table><tr><th>ID</th><th>Family</th><th>Score</th>{header}</tr>{rows}</table><h2>Verification</h2><table><tr><th>Candidate</th><th>Passed</th><th>Reason</th></tr>{checks}</table><details><summary>Pruned proposals ({len(transition.explanation.rejected_candidates) if transition.explanation else 0})</summary><ul>{rejections}</ul></details></html>"""


def write_html(
    path: Path,
    script: MixScript,
    a: TrackAnalysis,
    b: TrackAnalysis,
    verifications: list[dict[str, object]],
) -> Path:
    path.write_text(render_html(script, a, b, verifications), encoding="utf-8")
    return path
