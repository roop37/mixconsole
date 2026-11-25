"""Analysis, cache management, environment diagnostics and MixScript validation."""

import importlib
import importlib.util
import platform
import shutil
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from mixconsole import __version__
from mixconsole.mixscript import load_mixscript

app = typer.Typer(no_args_is_help=True, help="Local-first, inspectable DJ transitions (pre-alpha).")
console = Console()


def _version(value: bool) -> None:
    if value:
        typer.echo(f"mixconsole {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version, is_eager=True, help="Show version and exit."),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
    quiet: Annotated[bool, typer.Option("--quiet", "-q", help="Errors only.")] = False,
) -> None:
    """Analyze tracks, validate MixScripts, benchmark, and inspect the environment."""
    import logging

    level = logging.DEBUG if verbose else logging.ERROR if quiet else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s", force=True)


def _package_status(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not installed"


@app.command()
def doctor() -> None:
    """Report Python, ffmpeg, optional packages and torch/MPS availability."""
    table = Table(title="MixConsole doctor")
    table.add_column("Component")
    table.add_column("Status")
    table.add_row("MixConsole", __version__)
    table.add_row("Python", platform.python_version())
    table.add_row("ffmpeg", shutil.which("ffmpeg") or "not found (SoundFile formats still work)")
    table.add_row("extra: neural / all", "optional Beat This!; run models fetch beat_this")
    for extra in ("stems", "ui"):
        table.add_row(f"extra: {extra}", "placeholder (future milestone)")
    for package in ("beat-this", "demucs", "fastapi", "torch"):
        table.add_row(package, _package_status(package))
    mps = "unavailable (torch not installed)"
    cuda = "unavailable (torch not installed)"
    if importlib.util.find_spec("torch") is not None:
        try:
            torch = importlib.import_module("torch")
            mps = "available" if torch.backends.mps.is_available() else "unavailable"
            cuda = "available" if torch.cuda.is_available() else "unavailable"
        except Exception as exc:
            mps = cuda = f"probe failed: {type(exc).__name__}: {exc}"
    table.add_row("MPS", mps)
    table.add_row("CUDA", cuda)
    console.print(table)


@app.command()
def validate(path: Annotated[Path, typer.Argument(help="MixScript JSON file.")]) -> None:
    """Validate schema fields and semantic track/cue references."""
    try:
        script = load_mixscript(path)
    except (OSError, UnicodeError, ValueError, ValidationError) as exc:
        typer.echo(f"Invalid MixScript: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        f"Valid {script.version}: {len(script.tracks)} tracks, "
        f"{len(script.transitions)} transitions"
    )


@app.command("analyze")
def analyze_command(
    files: Annotated[list[Path], typer.Argument(help="Audio files to analyze.")],
    html_output: Annotated[
        Path | None, typer.Option("--html", help="Write a standalone local analysis viewer.")
    ] = None,
    json_output: Annotated[
        Path | None, typer.Option("--json", help="Export JSON + sibling NPZ.")
    ] = None,
    no_cache: Annotated[bool, typer.Option("--no-cache")] = False,
    cache_dir: Annotated[Path | None, typer.Option("--cache-dir")] = None,
    beats: Annotated[str | None, typer.Option("--beats", help="librosa or beat_this")] = None,
    sections: Annotated[str | None, typer.Option("--sections", help="novelty or allin1")] = None,
    workers: Annotated[
        int | None,
        typer.Option("--workers", min=1, max=32, help="Parallel processes (config default)."),
    ] = None,
) -> None:
    """Analyze tempo, key, structure, loudness and edges with core DSP backends."""
    import json

    from rich.progress import Progress as Bar

    from mixconsole.analysis.cache import atomic_write, save_analysis
    from mixconsole.config import load_settings
    from mixconsole.report.html import render_analysis_html
    from mixconsole.service import ProgressEvent, analyze_tracks

    if html_output is not None and len(files) != 1:
        raise typer.BadParameter("--html requires exactly one audio file")
    settings = load_settings()
    chosen = dict(settings.backends)
    if beats:
        chosen["beats"] = beats
    if sections:
        chosen["sections"] = sections

    table = Table(title="Track analysis")
    for column in (
        "File",
        "BPM",
        "Key / Camelot",
        "LUFS",
        "Bars",
        "Phrases",
        "Sections",
        "H/T (s)",
    ):
        table.add_column(column, min_width=9 if column == "H/T (s)" else None)
    notes = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    results: list[dict[str, object]] = []
    try:
        with Bar(console=console, transient=True) as bar:
            task = bar.add_task("analyzing", total=1.0)

            def show(event: ProgressEvent) -> None:
                bar.update(task, completed=event.fraction, description=event.message or "analyzing")

            analyses = analyze_tracks(
                files,
                backends=chosen,
                use_cache=not no_cache,
                cache_dir=cache_dir or settings.cache_dir,
                workers=workers or settings.workers,
                progress=show,
            )
        for index, (file, result) in enumerate(zip(files, analyses, strict=True)):
            table.add_row(
                file.name,
                f"{result.global_bpm:.2f}" if result.global_bpm else "—",
                f"{notes[result.key.tonic]} {result.key.mode} / {result.key.camelot}",
                f"{result.loudness.integrated_lufs:.1f}"
                if result.loudness.integrated_lufs is not None
                else "silence",
                str(len(result.bars)),
                str(len(result.phrases)),
                str(len(result.sections)),
                f"{result.edges.silence_head:.2f}/{result.edges.silence_tail:.2f}",
            )
            if json_output:
                destination = (
                    json_output
                    if len(files) == 1
                    else json_output.with_name(f"{json_output.stem}-{index + 1}.json")
                )
                save_analysis(result, destination)
                if len(files) > 1:
                    results.append(json.loads(destination.read_text()))
        if json_output and len(files) > 1:
            atomic_write(
                json_output, (json.dumps(results, indent=2, allow_nan=False) + "\n").encode()
            )
        if html_output is not None:
            html_output.parent.mkdir(parents=True, exist_ok=True)
            atomic_write(
                html_output,
                render_analysis_html(analyses[0], files[0], html_output).encode("utf-8"),
            )
    except (OSError, ValueError, RuntimeError) as exc:
        typer.echo(f"Analysis failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    console.print(table)


cache_app = typer.Typer(help="Inspect or clear the local analysis cache.")
app.add_typer(cache_app, name="cache")

models_app = typer.Typer(help="Fetch checksum-pinned optional model checkpoints.")
app.add_typer(models_app, name="models")


@models_app.command("fetch")
def models_fetch_command(
    name: Annotated[str, typer.Argument(help="beat_this or htdemucs")],
) -> None:
    """Fetch an official, checksum-pinned checkpoint into the ignored cache."""
    from mixconsole.analysis import model_manager

    if name not in ("beat_this", "htdemucs"):
        raise typer.BadParameter("choose beat_this or htdemucs")
    try:
        if name == "beat_this":
            path, sha = model_manager.fetch_beat_this(), model_manager.BEAT_THIS_SHA256
        else:
            path, sha = model_manager.fetch_htdemucs(), model_manager.HTDEMUCS_SHA256
    except (OSError, ValueError) as exc:
        typer.echo(f"Model fetch failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"{path} sha256:{sha}")


@cache_app.command("info")
def cache_info_command(
    cache_dir: Annotated[Path | None, typer.Option("--cache-dir")] = None,
) -> None:
    from mixconsole.analysis.cache import cache_info, cache_root
    from mixconsole.config import load_settings

    root = cache_root(cache_dir if cache_dir is not None else load_settings().cache_dir)
    info = cache_info(root)
    typer.echo(f"{root}: {info['entries']} entries, {info['bytes']} bytes")


@cache_app.command("clear")
def cache_clear_command(
    cache_dir: Annotated[Path | None, typer.Option("--cache-dir")] = None,
) -> None:
    from mixconsole.analysis.cache import cache_root, clear_cache
    from mixconsole.config import load_settings

    root = cache_root(cache_dir if cache_dir is not None else load_settings().cache_dir)
    typer.echo(f"Cleared {clear_cache(root)} entries")


bench_app = typer.Typer(help="Run synthetic benchmarks or evaluate local public datasets.")
app.add_typer(bench_app, name="bench")
BENCH_OUT = Path("bench/results")


def _report(result_path: Path, compare_with: Path | None) -> None:
    from mixconsole.bench import BenchResult, compare

    typer.echo(f"Wrote {result_path} and {result_path.parent / 'LATEST.md'}")
    if compare_with is not None:
        old = BenchResult.model_validate_json(compare_with.read_text(encoding="utf-8"))
        new = BenchResult.model_validate_json(result_path.read_text(encoding="utf-8"))
        for line in compare(old, new):
            typer.echo(line)


@bench_app.command("perf")
def bench_perf_command(
    durations: Annotated[
        str, typer.Option(help="Comma-separated input lengths, s.")
    ] = "30,240,600",
    repeat: Annotated[int, typer.Option(min=1)] = 3,
    out: Annotated[Path, typer.Option(help="Results directory.")] = BENCH_OUT,
    compare_with: Annotated[Path | None, typer.Option("--compare")] = None,
) -> None:
    """Per-stage time and memory; writes a bench-result/v1 JSON and LATEST.md."""
    from mixconsole.bench import run_perf, write_result

    lengths = [int(part) for part in durations.split(",") if part.strip()]
    with console.status("benchmarking") as status:
        result = run_perf(lengths, repeat, progress=status.update)
    _report(write_result(result, out), compare_with)


@bench_app.command("accuracy")
def bench_accuracy_command(
    quick: Annotated[bool, typer.Option(help="Coarse grid for smoke runs.")] = False,
    beats: Annotated[str, typer.Option(help="librosa or beat_this.")] = "librosa",
    out: Annotated[Path, typer.Option(help="Results directory.")] = BENCH_OUT,
    compare_with: Annotated[Path | None, typer.Option("--compare")] = None,
) -> None:
    """Synthetic accuracy under noise, codec, timing and percussion changes."""
    from mixconsole.bench import run_accuracy, write_result

    with console.status("evaluating") as status:
        result = run_accuracy(quick=quick, beats=beats, progress=status.update)
    _report(write_result(result, out), compare_with)


config_app = typer.Typer(help="Show effective configuration.")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show_command() -> None:
    """Print the merged config (defaults < TOML file < MIXCONSOLE_* env) and its path."""
    from mixconsole.config import config_path, load_settings

    path = config_path()
    typer.echo(f"# {path} ({'found' if path.is_file() else 'not found, using defaults'})")
    typer.echo(load_settings().model_dump_json(indent=2))


@bench_app.command("dataset")
def bench_dataset_command(
    name: Annotated[
        str,
        typer.Argument(help="ballroom, gtzan_rhythm, giantsteps_key, giantsteps_tempo, cc_sanity"),
    ],
    audio_dir: Annotated[
        Path | None, typer.Option(help="Local audio directory (public datasets).")
    ] = None,
    annotations_dir: Annotated[
        Path | None, typer.Option(help="Local annotation directory.")
    ] = None,
    out: Annotated[Path, typer.Option(help="Results directory.")] = BENCH_OUT,
    fetch: Annotated[bool, typer.Option(help="Fetch reviewed CC audio into the cache.")] = False,
    beats: Annotated[str, typer.Option(help="librosa or beat_this.")] = "librosa",
) -> None:
    """Evaluate local public-dataset files, or print acquisition/layout instructions."""
    from mixconsole.bench.datasets import instructions, run_dataset
    from mixconsole.bench.results import write_result

    try:
        if name == "cc_sanity":
            from mixconsole.bench.cc_sanity import run_cc_sanity

            with console.status("evaluating CC sanity tracks"):
                result = run_cc_sanity(fetch=fetch, beats=beats)
            _report(write_result(result, out), None)
            return
        if audio_dir is None:
            raise ValueError("--audio-dir is required for this dataset")
        guide = instructions(name, audio_dir, annotations_dir)
        annotation_root = annotations_dir or audio_dir / "annotations"
        if not audio_dir.is_dir() or not annotation_root.is_dir():
            typer.echo(guide)
            return
        with console.status("evaluating dataset"):
            result = run_dataset(name, audio_dir, annotations_dir)
        _report(write_result(result, out), None)
    except (ValueError, OSError) as exc:
        typer.echo(f"Dataset error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@app.command("mix")
def mix_command(
    a: Annotated[Path, typer.Argument(help="Outgoing audio file")],
    b: Annotated[Path, typer.Argument(help="Incoming audio file")],
    out: Annotated[Path, typer.Option("-o", help="Rendered WAV or FLAC path")],
    style: Annotated[str, typer.Option(help="auto, smooth, or club")] = "auto",
    candidates: Annotated[int, typer.Option(min=1, max=60)] = 3,
    report_dir: Annotated[Path | None, typer.Option()] = None,
    format: Annotated[str | None, typer.Option(help="wav or flac")] = None,
) -> None:
    """Render a two-song mix with audition candidates and a local report."""
    from mixconsole.service import mix_pair

    if format is not None:
        if format not in ("wav", "flac"):
            raise typer.BadParameter("format must be wav or flac")
        out = out.with_suffix("." + format)
    try:
        result = mix_pair(a, b, style=style, candidates=candidates, out=out, report_dir=report_dir)
    except (ValueError, OSError, RuntimeError) as exc:
        typer.echo(f"Mix failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"{result.paths['audio']}\n{result.paths['report_html']}")


@app.command("plan")
def plan_command(
    a: Annotated[Path, typer.Argument()],
    b: Annotated[Path, typer.Argument()],
    json_output: Annotated[Path, typer.Option("--json")],
    style: Annotated[str, typer.Option()] = "auto",
) -> None:
    """Write a ranked MixScript v1.1 without rendering."""
    from mixconsole.mixscript import dumps_mixscript
    from mixconsole.service import plan_pair

    try:
        result = plan_pair(a, b, style=style)
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(dumps_mixscript(result.mixscript), encoding="utf-8")
    except (ValueError, OSError, RuntimeError) as exc:
        typer.echo(f"Plan failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(str(json_output))


@app.command("render")
def render_command(
    plan: Annotated[Path, typer.Argument(help="MixScript v1.1 JSON")],
    track: Annotated[list[str], typer.Option("--track", help="deck_a=path or deck_b=path")],
    out: Annotated[Path, typer.Option("-o")],
) -> None:
    """Render a saved plan only when both canonical PCM hashes match."""
    from mixconsole.io import load_audio, write_audio
    from mixconsole.render import render_transition

    script = load_mixscript(plan)
    bindings = dict(item.split("=", 1) for item in track if "=" in item)
    if set(bindings) != {"deck_a", "deck_b"}:
        raise typer.BadParameter("supply --track deck_a=A and --track deck_b=B")
    left = load_audio(bindings["deck_a"])
    right = load_audio(bindings["deck_b"])
    if (
        left.pcm_sha256 != script.tracks["deck_a"].content_sha256
        or right.pcm_sha256 != script.tracks["deck_b"].content_sha256
    ):
        typer.echo("Track PCM hash mismatch", err=True)
        raise typer.Exit(code=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    stems = None
    if script.transitions[0].family in ("stem_handoff", "vocal_over_instrumental"):
        from mixconsole.analysis import analyze
        from mixconsole.config import load_settings
        from mixconsole.service import stems_for

        folder = load_settings().cache_dir
        try:
            stems = (
                stems_for(analyze(bindings["deck_a"]), left.samples, "exit", folder),
                stems_for(analyze(bindings["deck_b"]), right.samples, "entry", folder),
            )
        except ValueError as exc:
            typer.echo(f"Render failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc
    write_audio(out, render_transition(left.samples, right.samples, script, stems=stems))
    typer.echo(str(out))


@bench_app.command("transitions")
def bench_transitions_command(
    quick: Annotated[bool, typer.Option(help="Run two smoke pairs.")] = False,
    out: Annotated[Path, typer.Option(help="Results directory.")] = BENCH_OUT,
) -> None:
    """Run synthetic transition pairs and a plain 6-second linear crossfade baseline."""
    from mixconsole.bench.results import write_result
    from mixconsole.bench.transitions import run_transitions

    result = run_transitions(quick=quick)
    _report(write_result(result, out), None)


@bench_app.command("corpus")
def bench_corpus_command(
    limit: Annotated[int | None, typer.Option(min=1, help="Run only the first N pairs.")] = None,
    quick: Annotated[bool, typer.Option(help="Smoke run: 3 pairs.")] = False,
    systems: Annotated[
        str,
        typer.Option(help="Comma list of linear6,trim_eqpower,smooth,auto,club,automix_engine."),
    ] = "linear6,trim_eqpower,smooth,auto,club",
    budget_minutes: Annotated[
        float | None, typer.Option(help="Stop starting new pairs after this many minutes.")
    ] = None,
    fetch: Annotated[bool, typer.Option(help="Fetch the CC audio into the cache first.")] = False,
    pairs_file: Annotated[
        Path | None, typer.Option("--pairs", help="Alternative pairs.yaml.")
    ] = None,
    excerpts: Annotated[
        Path | None, typer.Option(help="Where to write listening excerpts (default: cache).")
    ] = None,
    out: Annotated[Path, typer.Option(help="Results directory.")] = BENCH_OUT,
) -> None:
    """Render every corpus pair with every system; write results, LATEST.md and listen input."""
    from mixconsole.bench import corpus as bc
    from mixconsole.bench.results import write_result

    chosen = tuple(item.strip() for item in systems.split(",") if item.strip())
    unknown = set(chosen) - {*bc.SYSTEMS, *bc.EXTERNAL}
    if unknown or not chosen:
        raise typer.BadParameter(f"unknown systems: {sorted(unknown)}")
    manifest = bc.load_corpus(pairs_file or bc.PAIRS)
    audio = bc.corpus_audio_dir()
    if fetch:
        with console.status("fetching CC corpus"):
            failures = bc.fetch_corpus(manifest, audio)
        for failure in failures:
            typer.echo(f"Fetch failed {failure}", err=True)
    folder = excerpts or bc.cache_root() / "corpus" / "excerpts"
    result, rows = bc.run_corpus(
        manifest,
        audio,
        systems=chosen,
        limit=3 if quick and limit is None else limit,
        budget_minutes=budget_minutes,
        excerpts=folder,
        log=typer.echo,
    )
    path = write_result(result, out)
    rows_path = bc.write_rows(
        out / "rows" / path.name.replace("-corpus-", "-corpus-rows-"), manifest, rows
    )
    typer.echo(f"Listening input: {bc.listen_input(manifest, rows, folder, chosen)}")
    typer.echo(f"Rows: {rows_path}")
    _report(path, None)


listen_app = typer.Typer(help="Offline blind listening kit (A/B + MUSHRA-lite) and its results.")
app.add_typer(listen_app, name="listen")


@listen_app.command("build")
def listen_build_command(
    out: Annotated[Path, typer.Option("-o", help="Kit folder to create.")],
    input_json: Annotated[
        Path | None, typer.Option("--input", help="listen-input.json written by bench corpus.")
    ] = None,
    synthetic: Annotated[bool, typer.Option(help="Use tiny synthetic clips (demo).")] = False,
    challenger: Annotated[str, typer.Option(help="System compared against all others.")] = "auto",
    seed: Annotated[int, typer.Option(help="Seed for tokens and A/B sides.")] = 2026,
    embed: Annotated[bool, typer.Option(help="Embed audio as data URIs (one HTML file).")] = False,
) -> None:
    """Create a self-contained local page with blind A/B pairs and a MUSHRA-lite rating page."""
    from mixconsole.listen import build_kit, synthetic_input

    try:
        if synthetic:
            input_json = synthetic_input(out / "_synthetic")
            challenger = "trim_eqpower" if challenger == "auto" else challenger
        if input_json is None:
            from mixconsole.bench.corpus import cache_root

            input_json = cache_root() / "corpus" / "excerpts" / "listen-input.json"
        page = build_kit(input_json, out, challenger=challenger, seed=seed, embed=embed)
    except (ValueError, OSError) as exc:
        typer.echo(f"Listen build failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"{page}\nSave raters' vote files into {out / 'votes'} (or pass them to results).")


@listen_app.command("results")
def listen_results_command(
    kit: Annotated[Path, typer.Argument(help="Kit folder (holds key.json).")],
    votes: Annotated[list[Path] | None, typer.Argument(help="Vote JSON files.")] = None,
    screen: Annotated[
        bool, typer.Option(help="Drop raters failing the hidden-reference check.")
    ] = True,
) -> None:
    """Win rates and MUSHRA-lite means with bootstrap confidence intervals."""
    from mixconsole.listen.stats import render_markdown, results_for_kit

    try:
        result = results_for_kit(kit, votes, screen=screen)
    except (ValueError, OSError, KeyError) as exc:
        typer.echo(f"Listen results failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    (kit / "results.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    markdown = render_markdown(result)
    (kit / "results.md").write_text(markdown, encoding="utf-8")
    typer.echo(markdown)
