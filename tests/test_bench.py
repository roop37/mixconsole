"""Bench harness: metric correctness, result format, LATEST.md and CLI wiring."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mixconsole.bench import compare, load_results, run_perf, write_result
from mixconsole.bench.metrics import beat_f_measure, mirex_key_score, tempo_acc1, tempo_acc2
from mixconsole.bench.results import schema_json
from mixconsole.cli import app

ROOT = Path(__file__).resolve().parents[1]


def test_beat_f_measure_hand_computed():
    assert beat_f_measure([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 1.0
    # 2 hits of 3 estimated and 4 reference: 2*2/(3+4)
    assert beat_f_measure([1.0, 2.05, 3.5], [1.0, 2.0, 3.0, 4.0]) == pytest.approx(4 / 7)
    assert beat_f_measure([], []) == 1.0
    assert beat_f_measure([1.0], []) == 0.0
    # one-to-one: two estimates near one reference count once
    assert beat_f_measure([1.0, 1.01], [1.0]) == pytest.approx(2 / 3)


def test_tempo_accuracy():
    assert tempo_acc1(124.0, 120.0)
    assert not tempo_acc1(125.0, 120.0)
    assert tempo_acc2(240.0, 120.0)
    assert tempo_acc2(60.0, 120.0)
    assert tempo_acc2(40.0, 120.0)
    assert not tempo_acc1(None, 120.0)
    assert not tempo_acc2(90.0, 120.0)


@pytest.mark.parametrize(
    ("est", "ref", "score"),
    [
        ((0, "major"), (0, "major"), 1.0),
        ((7, "major"), (0, "major"), 0.5),  # G vs C: fifth
        ((5, "minor"), (0, "minor"), 0.5),  # F minor vs C minor: fourth/fifth
        ((9, "minor"), (0, "major"), 0.3),  # A minor relative of C major
        ((0, "major"), (9, "minor"), 0.3),  # C major relative of A minor
        ((0, "minor"), (0, "major"), 0.2),  # parallel
        ((1, "major"), (0, "major"), 0.0),
    ],
)
def test_mirex_key_score(est, ref, score):
    assert mirex_key_score(*est, *ref) == score


def test_perf_result_written_and_compared(tmp_path):
    result = run_perf(durations=(8,), repeat=1)
    assert result.metrics["analyze_cold_8s"] > 0
    assert result.metrics["realtime_factor_8s"] > 1
    path = write_result(result, tmp_path)
    assert json.loads(path.read_text())["version"] == "bench-result/v1"
    latest = (tmp_path / "LATEST.md").read_text()
    assert "## perf" in latest
    assert "analyze_cold_8s" in latest
    assert load_results(tmp_path)[0] == result
    slower = result.model_copy(
        update={"metrics": {**result.metrics, "decode_8s": result.metrics["decode_8s"] + 1.0}}
    )
    assert any("REGRESSION" in line for line in compare(result, slower))


def test_latest_keeps_each_beat_backend(tmp_path):
    from mixconsole.bench.results import new_result

    core = new_result("accuracy", {"tempo_acc1_clean": 1.0}, parameters={"beats": "librosa"})
    neural = core.model_copy(update={"parameters": {"beats": "beat_this"}})
    write_result(core, tmp_path)
    write_result(neural, tmp_path)
    latest = (tmp_path / "LATEST.md").read_text()
    assert "## accuracy (librosa)" in latest
    assert "## accuracy (beat_this)" in latest


def test_committed_bench_schema_matches():
    assert (ROOT / "schemas/bench-result-v1.json").read_text() == schema_json()


def test_cli_bench_perf(tmp_path):
    out = tmp_path / "results"
    run = CliRunner().invoke(
        app, ["bench", "perf", "--durations", "6", "--repeat", "1", "--out", str(out)]
    )
    assert run.exit_code == 0, run.output
    assert (out / "LATEST.md").exists()
    assert len(list(out.glob("*.json"))) == 1


def test_compare_direction_and_noise_floor(tmp_path):
    from mixconsole.bench.results import _is_regression

    assert _is_regression("analyze_cold_240s", 1.0, 1.5, 0.2)
    assert not _is_regression("analyze_cold_240s", 1.5, 1.0, 0.2)
    assert not _is_regression("analyze_cache_hit_30s", 0.007, 0.013, 0.2)  # jitter
    assert _is_regression("peak_heap_mib_240s", 500, 700, 0.2)
    assert not _is_regression("realtime_factor_240s", 100, 150, 0.2)  # faster is good
    assert _is_regression("realtime_factor_240s", 150, 100, 0.2)


def test_machine_fingerprint_when_host_probes_are_unavailable(monkeypatch):
    from mixconsole.bench import results

    monkeypatch.setattr(results.platform, "system", lambda: "Linux")
    monkeypatch.setattr(results.platform, "processor", lambda: "")
    monkeypatch.setattr(results.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(results.os, "cpu_count", lambda: None)

    def missing_sysconf(_name):
        raise OSError("unavailable")

    monkeypatch.setattr(results.os, "sysconf", missing_sysconf)
    machine = results.machine_fingerprint()
    assert machine.processor == "aarch64"
    assert machine.cpu_count == 1
    assert machine.ram_bytes is None


def test_result_reader_skips_unrelated_json_and_compare_handles_zero(tmp_path):
    from mixconsole.bench.results import new_result

    (tmp_path / "unrelated.json").write_text('{"unrelated": true}')
    assert load_results(tmp_path) == []
    old = new_result("perf", {"decode_30s": 0.0})
    new = old.model_copy(update={"metrics": {"decode_30s": 1.0, "new_metric": 1.0}})
    assert compare(old, new) == []


def test_tiny_accuracy_grid_runs_every_path_and_hits_targets():
    from mixconsole.bench.accuracy import run_accuracy

    result = run_accuracy(tiny=True)
    metrics = result.metrics
    assert result.parameters["tiny"] == 1
    assert metrics["tempo_acc1_clean"] == 1.0
    assert metrics["beat_f_mean_clean"] > 0.9
    assert metrics["key_exact_rate_snr20"] == 1.0
    assert metrics["phrase_exact_rate"] == 1.0
    assert metrics["meter_3_4_rate_snr20"] == 1.0
    assert metrics["sections_breakdown_exact_snr20"] == 1.0
    assert result.backends["vocals"].startswith("heuristic@")
    assert metrics["lufs_error_max"] < 1.0
