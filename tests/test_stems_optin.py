"""M3.1: stems are opt-in (off | auto | on), gated in auto, and checked for separation bleed."""

from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from mixconsole.analysis.backends import stems as stem_backend
from mixconsole.cli import app
from mixconsole.config import Settings
from mixconsole.io import SAMPLE_RATE
from mixconsole.plan.candidates import plan_pair
from mixconsole.render.graph import STEM_FAMILIES, RenderInspection
from mixconsole.service import mix_pair
from mixconsole.verify.metrics import stem_leakage, verify_seam
from tests import test_m3
from tests.test_m3 import Pair, clash, pair  # noqa: F401  (module-scoped fixtures)


def mode(value: str, **extra: float) -> Settings:
    return Settings().model_copy(update={"stems": value, **extra})


def stem_ids(result_candidates: list) -> list:  # type: ignore[type-arg]
    return [c for c in result_candidates if c.family in STEM_FAMILIES]


def test_default_is_off_and_marks_stem_families_disabled(pair: Pair) -> None:  # noqa: F811
    assert Settings().stems == "off"
    plan = plan_pair(pair.a, pair.b, Settings())
    assert not stem_ids(plan.candidates)
    reasons = {r.family: r.reason for r in plan.rejected if r.candidate_id.endswith("_na")}
    assert reasons["stem_handoff"] == reasons["vocal_over_instrumental"] == "stems disabled"
    assert "stems disabled" in plan.stem_note


def test_off_never_separates(
    pair: Pair,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class Forbidden:
        name, version = "forbidden", "1"

        def separate(self, audio: np.ndarray, start_frame: int) -> dict[str, np.ndarray]:
            raise AssertionError("separation must not run when stems are off")

    monkeypatch.setattr(stem_backend, "_separator", Forbidden())
    monkeypatch.setenv("MIXCONSOLE_STEMS", "off")
    monkeypatch.setenv("MIXCONSOLE_WORKERS", "1")
    monkeypatch.setenv("MIXCONSOLE_CACHE_DIR", str(tmp_path / "fresh-cache"))
    monkeypatch.setenv("MIXCONSOLE_CANDIDATES_PER_FAMILY", "2")
    monkeypatch.setenv("MIXCONSOLE_MAX_CANDIDATES", "8")
    result = mix_pair(
        pair.path_a, pair.path_b, out=tmp_path / "m.wav", report_dir=tmp_path / "r", candidates=2
    )
    assert result.mixscript.transitions[0].family not in STEM_FAMILIES
    explanation = result.mixscript.transitions[0].explanation
    assert explanation is not None
    assert "stems disabled" in explanation.chosen_because


def test_cli_stems_option_sets_the_mode(
    pair: Pair,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen: list[str] = []

    def fake(*args: object, **kwargs: object) -> None:
        import os

        seen.append(os.environ["MIXCONSOLE_STEMS"])
        raise ValueError("stop")

    monkeypatch.setattr("mixconsole.service.mix_pair", fake)
    runner = CliRunner()
    base = ["mix", str(pair.path_a), str(pair.path_b), "-o", str(tmp_path / "x.wav")]
    assert runner.invoke(app, [*base, "--stems", "auto"]).exit_code == 1
    assert seen == ["auto"]
    bad = runner.invoke(app, [*base, "--stems", "maybe"])
    assert bad.exit_code != 0


@pytest.fixture(scope="module")
def calm(tmp_path_factory: pytest.TempPathFactory) -> Pair:
    """Compatible keys and no vocal collision: nothing for stems to fix."""
    patch = pytest.MonkeyPatch()
    patch.setattr(test_m3, "B_VOCALS", (28, 29, 30, 31))
    built = Pair(tmp_path_factory.mktemp("m31-calm"))
    built.build(patch)
    patch.undo()
    return built


def test_auto_without_key_clash_prefers_plain_families(calm: Pair) -> None:
    plan = plan_pair(calm.a, calm.b, mode("auto"))
    assert not stem_ids(plan.candidates)
    assert plan.candidates[0].family not in STEM_FAMILIES
    assert "declined" in plan.stem_note
    assert any(r.candidate_id.endswith("_auto") for r in plan.rejected)


def test_auto_allows_stems_for_a_vocal_collision_plain_blends_cannot_avoid(
    pair: Pair,  # noqa: F811
) -> None:
    plan = plan_pair(pair.a, pair.b, mode("auto", stems_auto_margin=0.0))
    assert stem_ids(plan.candidates)
    assert "vocal collision" in plan.stem_note


def test_auto_with_key_clash_and_margin_allows_stems(clash: Pair) -> None:  # noqa: F811
    plan = plan_pair(clash.a, clash.b, mode("auto", stems_auto_margin=0.0))
    assert stem_ids(plan.candidates)
    assert "key clash" in plan.stem_note
    assert "allowed" in plan.stem_note
    blocked = plan_pair(clash.a, clash.b, mode("auto", stems_auto_margin=1.0))
    assert not stem_ids(blocked.candidates)
    assert "does not beat best plain" in blocked.stem_note


def test_on_keeps_stem_families_competing(pair: Pair) -> None:  # noqa: F811
    assert stem_ids(plan_pair(pair.a, pair.b, mode("on")).candidates)


def _stems(leak: float) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(3)
    n = SAMPLE_RATE * 2

    def stereo(x: np.ndarray) -> np.ndarray:
        return np.stack((x, x), axis=1).astype(np.float32)

    drums, bass, other, voice = (rng.standard_normal(n) * 0.1 for _ in range(4))
    sources: dict[str, np.ndarray] = {}
    for deck in ("a", "b"):
        sources[f"{deck}:drums"] = stereo(drums)
        sources[f"{deck}:bass"] = stereo(bass)
        sources[f"{deck}:other"] = stereo(other)
        sources[f"{deck}:vocals"] = stereo(voice + leak * drums)
    return sources


def test_leakage_clean_vs_leaky_and_unmeasured() -> None:
    clean = stem_leakage(RenderInspection(stem_sources=_stems(0.0)))
    leaky = stem_leakage(RenderInspection(stem_sources=_stems(1.0)))
    assert clean is not None
    assert clean < 0.1
    assert leaky is not None
    assert leaky > 0.5
    assert stem_leakage(None) is None
    assert stem_leakage(RenderInspection()) is None
    silent = {k: np.zeros_like(v) for k, v in _stems(0.0).items()}
    assert stem_leakage(RenderInspection(stem_sources=silent)) is None  # unmeasured, not 0


def test_verify_fails_a_leaky_stem_seam_and_threshold_is_configurable() -> None:
    frames = SAMPLE_RATE * 4
    tone = (0.2 * np.sin(2 * np.pi * 220 * np.arange(frames) / SAMPLE_RATE)).astype(np.float32)
    mix = np.stack((tone, tone), axis=1)
    inspection = RenderInspection(stem_sources=_stems(1.0))
    failed = verify_seam(mix, frames // 2, 0, bpm=120.0, inspection=inspection)
    assert not failed.passed
    assert "stem leakage" in failed.reason
    assert failed.stem_leakage is not None
    relaxed = verify_seam(
        mix, frames // 2, 0, bpm=120.0, inspection=inspection, max_stem_leakage=1.0
    )
    assert "stem leakage" not in relaxed.reason
    assert verify_seam(mix, frames // 2, 0, bpm=120.0).stem_leakage is None
