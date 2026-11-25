"""Compile a v1.1 transition into a deterministic stereo PCM handoff."""

from dataclasses import dataclass, field

import numpy as np

from mixconsole.analysis.backends.stems import STEM_NAMES, StemSet, compensate
from mixconsole.io import SAMPLE_RATE, Audio
from mixconsole.mixscript.models import MixScript
from mixconsole.render.eq import bands, isolate_mid_high
from mixconsole.render.gain import curve, lane_curve
from mixconsole.render.limiter import limit
from mixconsole.render.stretch import ramp_back, stretch, stretch_piecewise


@dataclass
class RenderInspection:
    """Unmixed overlap signals for audio-derived seam checks."""

    source_b: Audio | None = None
    stretched_b: Audio | None = None
    contribution_a: Audio | None = None
    contribution_b: Audio | None = None
    beat_warp: list[list[int]] | None = None
    # Post-automation stem signals, keyed "a:vocals", "b:bass", ... (stem families only).
    stem_contributions: dict[str, Audio] = field(default_factory=dict[str, Audio])


def _frame(seconds: float, maximum: int) -> int:
    return max(0, min(maximum, round(seconds * SAMPLE_RATE)))


STEM_FAMILIES = ("stem_handoff", "vocal_over_instrumental")


def family_is_matched(family: str, strategy: str) -> bool:
    return (family == "beatmatch_blend" or family in STEM_FAMILIES) and strategy != "no_sync"


def _fit(audio: Audio, frames: int) -> Audio:
    if len(audio) == frames:
        return audio
    return np.pad(audio, ((0, frames - len(audio)), (0, 0)))


def render_transition(
    a: Audio,
    b: Audio,
    script: MixScript,
    *,
    inspection: RenderInspection | None = None,
    stems: tuple[StemSet, StemSet] | None = None,
) -> Audio:
    """Untouched source regions are copied by slice before the seam and after it.

    ``stems`` are the separated windows of A and B in the coordinates of ``a``/``b``;
    they are required for the stem families and used only inside the transition.
    """
    transition = script.transitions[0]
    if transition.family in STEM_FAMILIES and stems is None:
        raise ValueError(f"{transition.family} needs separated stems (stems extra)")
    xa, xb = _frame(transition.exit.seconds, len(a)), _frame(transition.entry.seconds, len(b))
    bpm = transition.tempo.tempo_map[0].bpm if transition.tempo.tempo_map else 120.0
    frames = round(transition.length_bars * transition.beats_per_bar * 60 / bpm * SAMPLE_RATE)
    if frames <= 0:
        joined = np.concatenate((a[:xa], b[xb:]))
        return limit(joined)
    end_a = min(len(a), xa + frames)
    source_a = a[xa:end_a]
    match = next((effect for effect in transition.effects if effect.name == "tempo_match"), None)
    effective_bpm = float(match.params.get("effective_bpm", bpm)) if match else bpm
    beat_warp = transition.extensions.get("render.beat_warp")
    source_frames = (
        int(beat_warp[-1][0])
        if beat_warp
        else round(frames * bpm / effective_bpm)
        if family_is_matched(transition.family, transition.tempo.strategy)
        else frames
    )
    source_b = b[xb : min(len(b), xb + source_frames)]
    if len(source_a) != frames:
        source_a = np.pad(source_a, ((0, frames - len(source_a)), (0, 0)))
    consumed_b = len(source_b)
    source_b_raw = source_b
    if inspection is not None:
        inspection.source_b = source_b.copy()
        inspection.beat_warp = beat_warp
    if beat_warp:
        source_b = stretch_piecewise(source_b, beat_warp)
    elif len(source_b) != frames:
        source_b = stretch(source_b, frames)
    if inspection is not None:
        inspection.stretched_b = source_b.copy()
    for effect in transition.effects:
        if effect.name == "gain_match" and effect.target.track == transition.to_track:
            db = float(effect.params.get("db", 0.0))
            source_b = source_b * np.float32(10 ** (db / 20))
    family = transition.family
    lanes = {
        lane.target.track: lane
        for lane in transition.automation
        if lane.parameter == "gain" and lane.target.kind == "track"
    }
    fade_a = (
        lane_curve(lanes[transition.from_track], frames, bpm)
        if transition.from_track in lanes
        else curve(frames, "equal_power")
    )
    fade_b = (
        lane_curve(lanes[transition.to_track], frames, bpm)
        if transition.to_track in lanes
        else curve(frames, "equal_power", incoming=True)
    )
    # Equal-power gains over-amplify identical correlated signals by 3 dB.
    dot = np.sum(source_a * source_b)
    norm = np.sqrt(np.sum(source_a * source_a) * np.sum(source_b * source_b) + 1e-12)
    correlation = float(dot / norm)
    if correlation > 0.9:
        fade_a = curve(frames, "linear")
        fade_b = curve(frames, "linear", incoming=True)
    if family in STEM_FAMILIES:
        assert stems is not None
        gain_b = np.float32(1.0)
        for effect in transition.effects:
            if effect.name == "gain_match" and effect.target.track == transition.to_track:
                gain_b = np.float32(10 ** (float(effect.params.get("db", 0.0)) / 20))
        stem_lanes = {
            (lane.target.track, lane.target.stem): lane_curve(lane, frames, bpm)
            for lane in transition.automation
            if lane.parameter == "gain" and lane.target.kind == "stem"
        }
        a_set, b_set = compensate(stems[0]), compensate(stems[1])
        a_stems = a_set.slice(xa, xa + frames)
        b_stems = b_set.slice(xb, xb + len(source_b_raw))
        contribution_a = np.zeros((frames, 2), dtype=np.float32)
        contribution_b = np.zeros((frames, 2), dtype=np.float32)
        unity = np.ones(frames, dtype=np.float32)
        for name in STEM_NAMES:
            part_a = _fit(a_stems[name], frames)
            part_b = b_stems[name]
            part_b = (
                stretch_piecewise(part_b, beat_warp) if beat_warp else stretch(part_b, frames)
            ) * gain_b
            ga = stem_lanes.get((transition.from_track, name), unity)
            gb = stem_lanes.get((transition.to_track, name), unity)
            ca, cb = part_a * ga[:, None], part_b * gb[:, None]
            contribution_a += ca
            contribution_b += cb
            if inspection is not None:
                inspection.stem_contributions[f"a:{name}"] = ca
                inspection.stem_contributions[f"b:{name}"] = cb
        mixed = contribution_a + contribution_b
    elif family == "beatmatch_blend":
        al, am, ah = bands(source_a)
        bl, bm, bh = bands(source_b)
        swap_effect = next(
            (effect for effect in transition.effects if effect.name == "bass_swap"), None
        )
        swap_beat = (
            float(
                swap_effect.params.get(
                    "beat", transition.length_bars * transition.beats_per_bar / 2
                )
            )
            if swap_effect
            else transition.length_bars * transition.beats_per_bar / 2
        )
        swap = max(0, min(frames, round(swap_beat * 60 / bpm * SAMPLE_RATE)))
        low_a = np.ones(frames, dtype=np.float32)
        low_a[swap:] = 0
        low_b = 1 - low_a
        contribution_a = al * low_a[:, None] + isolate_mid_high(am + ah) * fade_a[:, None]
        contribution_b = bl * low_b[:, None] + isolate_mid_high(bm + bh) * fade_b[:, None]
        mixed = contribution_a + contribution_b
    else:
        if family == "filter_sweep":
            from mixconsole.render.filters import sweep

            filter_effect = next(
                (effect for effect in transition.effects if effect.name == "filter_sweep"), None
            )
            start_hz = float(filter_effect.params.get("start_hz", 40.0)) if filter_effect else 40.0
            end_hz = float(filter_effect.params.get("end_hz", 8000.0)) if filter_effect else 8000.0
            source_a = sweep(source_a, start_hz, end_hz, "highpass")
            source_b = sweep(source_b, 200, 12000, "lowpass")
        contribution_a = source_a * fade_a[:, None]
        contribution_b = source_b * fade_b[:, None]
        mixed = contribution_a + contribution_b
        if family == "echo_out":
            from mixconsole.render.delay import echo

            echo_effect = next(
                (effect for effect in transition.effects if effect.name == "echo"), None
            )
            tail_beats = int(echo_effect.params.get("tail_beats", 2)) if echo_effect else 2
            feedback = float(echo_effect.params.get("feedback", 0.4)) if echo_effect else 0.4
            tail = echo(
                source_a[-min(frames, round(SAMPLE_RATE * 60 / bpm)) :], bpm, tail_beats, feedback
            )
            count = min(len(tail), frames)
            mixed[:count] += tail[:count] * np.float32(0.15)
    if inspection is not None:
        inspection.contribution_a = contribution_a
        inspection.contribution_b = contribution_b
    for effect in transition.effects:
        if effect.name == "seam_gain":
            boost = 10 ** (float(effect.params.get("db", 0.0)) / 20)
            envelope = np.sin(np.linspace(0, np.pi, frames, dtype=np.float32))
            mixed *= (1 + (boost - 1) * envelope)[:, None]
    post = np.empty((0, 2), dtype=np.float32)
    if match and transition.tempo.strategy == "ramp_b_to_a_then_back":
        post, used = ramp_back(
            b[xb + consumed_b :], effective_bpm, bpm, int(match.params.get("ramp_bars", 0))
        )
        consumed_b += used
    joined = np.concatenate(
        (a[:xa], mixed.astype(np.float32), post, b[min(len(b), xb + consumed_b) :])
    )
    return limit(joined)
