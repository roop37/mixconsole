"""Listening kit: offline page structure, blindness, votes -> win rates with CIs."""

import json
import random
import re

import pytest
from typer.testing import CliRunner

from mixconsole.cli import app
from mixconsole.listen import build_kit, synthetic_input
from mixconsole.listen import stats as ls


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    root = tmp_path_factory.mktemp("kit")
    source = synthetic_input(root / "in", pairs=3)
    page = build_kit(source, root / "kit", challenger="trim_eqpower", encode=False)
    return page.parent


def _config(kit_dir):
    html = (kit_dir / "index.html").read_text()
    return html, json.loads(
        re.search(r'id="kit" type="application/json">(.*?)</script>', html, re.S)[1]
    )


def test_page_is_offline_and_blind(kit):
    html, config = _config(kit)
    assert not re.search(r"https?://|//cdn|fetch\(|XMLHttpRequest|sendBeacon|WebSocket", html)
    assert "<link" not in html
    assert "<script src" not in html
    for name in ("linear6", "trim_eqpower", "crossfade4", "anchor"):
        assert name not in html.split('id="kit"')[1].split("</script>")[0]
        assert not any(name in f.name for f in (kit / "audio").iterdir())
    assert len(config["ab"]) == 3 * 2  # challenger vs the two other systems, per pair
    assert len(config["mushra"]) == 3
    assert all(len(m["items"]) == 3 + 2 for m in config["mushra"])  # systems + hidden ref + anchor
    for token in config["audio"]:
        assert (kit / config["audio"][token]).is_file()


def test_key_and_deterministic_sides(kit, tmp_path):
    key = json.loads((kit / "key.json").read_text())
    _, config = _config(kit)
    assert set(config["audio"]) == set(key["tokens"])
    systems = {v["system"] for v in key["tokens"].values()}
    assert {"reference", "reference_visible", "anchor", "linear6"} <= systems
    sides = {key["tokens"][t["left"]]["system"] for t in config["ab"]}
    assert len(sides) > 1 or len(config["ab"]) < 3  # sides are randomised
    again = build_kit(
        kit.parent / "in" / "listen-input.json",
        tmp_path / "k2",
        challenger="trim_eqpower",
        encode=False,
    )
    assert _config(again.parent)[1] == config


def test_embed_and_missing_audio(tmp_path):
    source = synthetic_input(tmp_path / "in", pairs=1)
    page = build_kit(source, tmp_path / "e", challenger="linear6", embed=True, encode=False)
    assert "data:audio/wav;base64," in page.read_text()
    assert not (tmp_path / "e" / "audio").exists()
    (tmp_path / "in" / "p0_ref.wav").unlink()
    with pytest.raises(ValueError, match="missing audio"):
        build_kit(source, tmp_path / "m", encode=False)


def test_encode_path_runs(tmp_path):
    source = synthetic_input(tmp_path / "in", pairs=1)
    page = build_kit(source, tmp_path / "enc", challenger="linear6")
    assert any(p.suffix in (".m4a", ".wav") for p in (page.parent / "audio").iterdir())


def _simulate(kit_dir, rater, p_win, seed, ref_score=100):
    key = json.loads((kit_dir / "key.json").read_text())
    _, config = _config(kit_dir)
    rng = random.Random(seed)
    ab = []
    for trial in config["ab"]:
        challenger_left = key["tokens"][trial["left"]]["system"] == key["challenger"]
        win = rng.random() < p_win
        choice = "left" if win == challenger_left else "right"
        ab.append(
            {
                **{k: trial[k] for k in ("pair", "left", "right")},
                "trial": trial["id"],
                "choice": choice,
            }
        )
    base = {
        "reference": ref_score,
        "anchor": 10,
        "linear6": 40,
        "trim_eqpower": 60,
        "crossfade4": 55,
    }
    mushra = [
        {"pair": m["pair"], "scores": {t: base[key["tokens"][t]["system"]] for t in m["items"]}}
        for m in config["mushra"]
    ]
    return {
        "version": "listen-votes/v1",
        "kit_id": key["kit_id"],
        "rater": rater,
        "ab": ab,
        "mushra": mushra,
    }


def test_results_win_rate_ci_and_screening(kit, tmp_path):
    votes = tmp_path / "votes"
    votes.mkdir()
    for index, (rater, p, ref) in enumerate([("a", 0.9, 100), ("b", 0.9, 95), ("cheat", 0.5, 20)]):
        (votes / f"{rater}.json").write_text(json.dumps(_simulate(kit, rater, p, index, ref)))
    files = sorted(votes.glob("*.json"))
    result = ls.analyze_votes(
        ls.Key.model_validate_json((kit / "key.json").read_text()),
        ls.load_votes(files, json.loads((kit / "key.json").read_text())["kit_id"]),
    )
    assert result.screened_out == ["cheat"]
    row = result.ab["linear6"]
    assert row.n == 9
    assert row.low <= row.mean <= row.high
    assert row.wins + row.losses + row.ties == row.n
    assert result.mushra["reference"].mean >= 95  # cheater excluded
    assert result.mushra["anchor"].mean < result.mushra["trim_eqpower"].mean
    text = ls.render_markdown(result)
    assert "linear6" in text
    assert "MUSHRA-lite" in text
    unscreened = ls.results_for_kit(kit, files, screen=False)
    assert unscreened.mushra["reference"].mean < result.mushra["reference"].mean


def test_bootstrap_ci_covers_and_is_seeded():
    low, high = ls.bootstrap_ci([1.0] * 30 + [0.0] * 10, seed=1)
    assert low < 0.75 < high
    assert (low, high) == ls.bootstrap_ci([1.0] * 30 + [0.0] * 10, seed=1)
    with pytest.raises(ValueError, match="no values"):
        ls.bootstrap_ci([])


def test_empty_results_print_na():
    key = ls.Key(kit_id="k", challenger="auto", tokens={})
    text = ls.render_markdown(ls.analyze_votes(key, []))
    assert text.count("n/a") >= 2
    assert "Raters: 0" in text


def test_vote_file_validation(kit, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"version": "x", "kit_id": "k", "rater": "r"}))
    with pytest.raises(ValueError, match="listen-votes"):
        ls.load_votes([bad], "k")
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"version": "listen-votes/v1", "kit_id": "zz", "rater": "r"}))
    with pytest.raises(ValueError, match="different kit"):
        ls.load_votes([other], "k")
    with pytest.raises(ValueError, match="no vote files"):
        ls.results_for_kit(kit, None)


def test_cli_build_and_results(tmp_path):
    out = tmp_path / "cli"
    run = CliRunner().invoke(app, ["listen", "build", "--synthetic", "-o", str(out)])
    assert run.exit_code == 0, run.output
    assert (out / "index.html").is_file()
    votes = out / "votes"
    votes.mkdir()
    (votes / "r.json").write_text(json.dumps(_simulate(out, "r", 1.0, 3)))
    res = CliRunner().invoke(app, ["listen", "results", str(out)])
    assert res.exit_code == 0, res.output
    assert "win rate" in res.output
    assert (out / "results.json").is_file()
    missing = CliRunner().invoke(app, ["listen", "results", str(tmp_path)])
    assert missing.exit_code == 1
    nothing = CliRunner().invoke(
        app, ["listen", "build", "-o", str(tmp_path / "x"), "--input", str(tmp_path / "nope.json")]
    )
    assert nothing.exit_code == 1
