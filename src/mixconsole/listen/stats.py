"""Vote analysis: A/B win rates and MUSHRA-lite means, both with seeded bootstrap CIs."""

import json
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

SCREEN_REFERENCE_MIN = 90.0
SCREEN_MAX_FAIL = 0.15


class ABVote(BaseModel):
    trial: str
    pair: str
    left: str
    right: str
    choice: str = Field(pattern=r"^(left|right|tie)$")


class MushraVote(BaseModel):
    pair: str
    scores: dict[str, float]


class Votes(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: str
    kit_id: str
    rater: str
    ab: list[ABVote] = Field(default_factory=list[ABVote])
    mushra: list[MushraVote] = Field(default_factory=list[MushraVote])


class Key(BaseModel):
    kit_id: str
    challenger: str
    tokens: dict[str, dict[str, str]]

    def system(self, token: str) -> str:
        return self.tokens[token]["system"]


class Interval(BaseModel):
    n: int
    mean: float
    low: float
    high: float


class ABRow(Interval):
    wins: int
    losses: int
    ties: int


class Analysis(BaseModel):
    kit_id: str
    challenger: str
    raters: list[str]
    screened_out: list[str]
    ab: dict[str, ABRow]
    mushra: dict[str, Interval]


def bootstrap_ci(
    values: list[float], *, seed: int = 0, resamples: int = 2000, level: float = 0.95
) -> tuple[float, float]:
    """Percentile bootstrap interval of the mean."""
    data = np.asarray(values, dtype=np.float64)
    if len(data) == 0:
        raise ValueError("no values")
    rng = np.random.default_rng(seed)
    means = data[rng.integers(0, len(data), (resamples, len(data)))].mean(axis=1)
    return float(np.quantile(means, (1 - level) / 2)), float(
        np.quantile(means, 1 - (1 - level) / 2)
    )


def load_votes(paths: list[Path], kit_id: str) -> list[Votes]:
    votes: list[Votes] = []
    for path in paths:
        vote = Votes.model_validate_json(path.read_text(encoding="utf-8"))
        if vote.version != "listen-votes/v1":
            raise ValueError(f"{path.name}: not a listen-votes/v1 file")
        if vote.kit_id != kit_id:
            raise ValueError(f"{path.name}: votes are for a different kit ({vote.kit_id})")
        votes.append(vote)
    return votes


def _screen(votes: list[Votes], key: Key) -> set[str]:
    """Raters whose hidden reference scores below 90 in more than 15 % of their sets."""
    flagged: set[str] = set()
    for vote in votes:
        scores = [
            score
            for entry in vote.mushra
            for token, score in entry.scores.items()
            if key.system(token) == "reference"
        ]
        if scores and sum(s < SCREEN_REFERENCE_MIN for s in scores) / len(scores) > SCREEN_MAX_FAIL:
            flagged.add(vote.rater)
    return flagged


def _interval(scores: list[float], seed: int) -> Interval:
    low, high = bootstrap_ci(scores, seed=seed)
    return Interval(n=len(scores), mean=float(np.mean(scores)), low=low, high=high)


def analyze_votes(key: Key, votes: list[Votes], *, screen: bool = True, seed: int = 0) -> Analysis:
    """Win rate of the challenger vs each baseline (tie = half a win) and MUSHRA means."""
    excluded = _screen(votes, key) if screen else set[str]()
    outcomes: dict[str, list[float]] = {}
    for vote in votes:
        for trial in vote.ab:
            left, right = key.system(trial.left), key.system(trial.right)
            if key.challenger not in (left, right):
                continue
            other = right if left == key.challenger else left
            if trial.choice == "tie":
                score = 0.5
            else:
                chosen = left if trial.choice == "left" else right
                score = 1.0 if chosen == key.challenger else 0.0
            outcomes.setdefault(other, []).append(score)
    ab = {
        other: ABRow(
            **_interval(scores, seed).model_dump(),
            wins=sum(s == 1.0 for s in scores),
            losses=sum(s == 0.0 for s in scores),
            ties=sum(s == 0.5 for s in scores),
        )
        for other, scores in sorted(outcomes.items())
    }
    ratings: dict[str, list[float]] = {}
    for vote in votes:
        if vote.rater in excluded:
            continue
        for entry in vote.mushra:
            for token, score in entry.scores.items():
                ratings.setdefault(key.system(token), []).append(score)
    return Analysis(
        kit_id=key.kit_id,
        challenger=key.challenger,
        raters=sorted(v.rater for v in votes),
        screened_out=sorted(excluded),
        ab=ab,
        mushra={name: _interval(scores, seed) for name, scores in sorted(ratings.items())},
    )


def render_markdown(result: Analysis) -> str:
    """Human-readable summary; no data prints ``n/a``, never 0."""
    lines = [
        f"# Listening results (kit {result.kit_id})",
        "",
        f"Raters: {len(result.raters)} ({', '.join(result.raters) or 'none'})",
    ]
    if result.screened_out:
        lines.append(
            f"Screened out of MUSHRA (hidden reference < 90 too often): {result.screened_out}"
        )
    lines += ["", f"## A/B: `{result.challenger}` vs each baseline", ""]
    lines += [
        "| baseline | n | wins | losses | ties | win rate | 95% CI |",
        "|---|---|---|---|---|---|---|",
    ]
    lines += [
        f"| {name} | {r.n} | {r.wins} | {r.losses} | {r.ties} | {r.mean:.2f} "
        f"| {r.low:.2f} - {r.high:.2f} |"
        for name, r in result.ab.items()
    ] or ["| n/a | n/a | n/a | n/a | n/a | n/a | n/a |"]
    lines += ["", "## MUSHRA-lite (0-100)", "", "| item | n | mean | 95% CI |", "|---|---|---|---|"]
    lines += [
        f"| {name} | {r.n} | {r.mean:.1f} | {r.low:.1f} - {r.high:.1f} |"
        for name, r in result.mushra.items()
    ] or ["| n/a | n/a | n/a | n/a |"]
    return "\n".join(lines) + "\n"


def results_for_kit(kit: Path, vote_files: list[Path] | None, *, screen: bool = True) -> Analysis:
    """Load ``key.json`` and the votes (default ``kit/votes/*.json``) and analyze them."""
    key = Key.model_validate(json.loads((kit / "key.json").read_text(encoding="utf-8")))
    files = vote_files or sorted((kit / "votes").glob("*.json"))
    if not files:
        raise ValueError(f"no vote files: save the page's JSON into {kit / 'votes'} or pass paths")
    return analyze_votes(key, load_votes(files, key.kit_id), screen=screen)
