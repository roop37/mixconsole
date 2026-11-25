import type { CandidateSummary, RejectedCandidate, Transition } from "@mixconsole/schema-ts";
import { candidateSourceKey, useAudition } from "../audition";
import { familyLabel, fmtNum, fmtScore, fmtTime, NA, titleCase } from "../lib/format";
import { barSeconds, transitionOf } from "../lib/mixscript";
import { checkFor, METRIC_LABELS, metricKeys, type Report, statusOf } from "../lib/report";
import { currentDoc } from "../state";
import { useStore } from "../store";
import { AuditionBar } from "./AuditionBar";

function isCurrent(transition: Transition, c: CandidateSummary): boolean {
  return (
    transition.family === c.family &&
    transition.length_bars === c.length_bars &&
    Math.abs(transition.exit.seconds - c.exit.seconds) < 0.01 &&
    Math.abs(transition.entry.seconds - c.entry.seconds) < 0.01
  );
}

export function PlanOptions() {
  const { state, dispatch, actions } = useStore();
  const { options } = state;
  const ready = Boolean(state.tracks.a && state.tracks.b && state.lanes.a && state.lanes.b);
  const busy = state.job?.state === "running" || state.job?.state === "queued";
  return (
    <form
      className="plan-options"
      aria-label="Plan options"
      onSubmit={(event) => {
        event.preventDefault();
        void actions.plan();
      }}
    >
      <label>
        Style
        <select
          className="input"
          value={options.style}
          onChange={(e) =>
            dispatch({ type: "options", patch: { style: e.target.value as typeof options.style } })
          }
        >
          <option value="auto">Auto</option>
          <option value="smooth">Smooth</option>
          <option value="club">Club</option>
        </select>
      </label>
      <label>
        Candidates
        <input
          className="input narrow"
          type="number"
          min={1}
          max={12}
          value={options.candidates}
          onChange={(e) =>
            dispatch({
              type: "options",
              patch: { candidates: Math.max(1, Math.min(12, Number(e.target.value) || 1)) },
            })
          }
        />
      </label>
      <label title="Stem separation: off (default), auto (only with a concrete reason) or on. Needs the stems extra.">
        Stems
        <select
          className="input"
          value={options.stems}
          onChange={(e) =>
            dispatch({ type: "options", patch: { stems: e.target.value as typeof options.stems } })
          }
        >
          <option value="off">Off (default)</option>
          <option value="auto">Auto</option>
          <option value="on">On</option>
        </select>
      </label>
      <button
        type="submit"
        className="btn primary"
        disabled={!ready || busy}
        aria-keyshortcuts="p"
        data-testid="plan"
      >
        {state.history.current ? "Plan again" : "Plan mix"}
      </button>
    </form>
  );
}

function MetricList({ metrics }: { metrics: Record<string, number | null> }) {
  return (
    <dl className="metrics">
      {metricKeys.map((key) => (
        <div key={key}>
          <dt>{METRIC_LABELS[key].label}</dt>
          <dd>
            {key === "clicks"
              ? (metrics[key] ?? NA)
              : fmtNum(metrics[key], 2, METRIC_LABELS[key].unit)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Breakdown({ values }: { values: Record<string, number> }) {
  const entries = Object.entries(values);
  if (entries.length === 0) return <p className="muted">Score breakdown: n/a</p>;
  return (
    <ul className="breakdown" aria-label="Score breakdown">
      {entries.map(([name, value]) => (
        <li key={name}>
          <span>{titleCase(name)}</span>
          <span className="bar" aria-hidden="true">
            <i style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
          </span>
          <span className="num">{fmtNum(value, 2)}</span>
        </li>
      ))}
    </ul>
  );
}

function Card({
  candidate,
  transition,
  report,
  rank,
}: {
  candidate: CandidateSummary;
  transition: Transition;
  report: Report | null;
  rank: number;
}) {
  const { state, dispatch, actions } = useStore();
  const audition = useAudition();
  const check = checkFor(report, candidate.id);
  const status = statusOf(check);
  const current = isCurrent(transition, candidate);
  const selected = state.selection.candidateId === candidate.id;
  const key = candidateSourceKey(candidate);
  const hasPreview = audition.sources.some((s) => s.key === key);
  const seconds = candidate.length_bars * barSeconds(transition);
  const busy = state.job?.state === "running" || state.job?.state === "queued";
  const statusText =
    status === "passed" ? "Verified" : status === "failed" ? "Failed" : "Not verified";
  return (
    <article
      className={`card${selected ? " selected" : ""}${current ? " current" : ""}`}
      aria-label={`Candidate ${rank}: ${familyLabel(candidate.family)}`}
      data-testid="candidate-card"
    >
      <header>
        <button
          type="button"
          className="card-select"
          aria-pressed={selected}
          onClick={() => dispatch({ type: "select", patch: { candidateId: candidate.id } })}
        >
          <span className="rank">#{rank}</span>
          <span className="family">{familyLabel(candidate.family)}</span>
        </button>
        {current && <span className="chip chip-current">In use</span>}
        <span className={`chip chip-${status}`} title={check?.reason || undefined}>
          {statusText}
        </span>
      </header>
      <div className="card-stats">
        <span>
          <b>{candidate.length_bars}</b> bars
          {candidate.length_bars ? ` · ${fmtNum(seconds, 1)} s` : ""}
        </span>
        <span>
          out {fmtTime(candidate.exit.seconds)} → in {fmtTime(candidate.entry.seconds)}
        </span>
        <span className="score" title="Weighted heuristic score">
          score <b>{fmtScore(candidate.score)}</b>
        </span>
      </div>
      <Breakdown values={candidate.score_breakdown ?? {}} />
      {status === "failed" && check?.reason && <p className="fail-reason">{check.reason}</p>}
      {check ? (
        <details>
          <summary>Seam measurements</summary>
          <MetricList metrics={check.metrics} />
        </details>
      ) : (
        <p className="muted">Seam measurements: n/a (not verified)</p>
      )}
      <footer>
        <button
          type="button"
          className="btn"
          disabled={!hasPreview}
          title={
            hasPreview
              ? "Play the 30 s preview around the handoff"
              : "No preview rendered for this candidate"
          }
          onClick={() => audition.playKey(key)}
        >
          Audition
        </button>
        <button
          type="button"
          className="btn"
          disabled={!hasPreview}
          aria-label={`Set candidate ${rank} as slot B`}
          onClick={() => audition.setSlot("b", key)}
        >
          Set as B
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={current || busy}
          onClick={() =>
            void actions.replan(
              {
                family: candidate.family,
                exit: candidate.exit.seconds,
                entry: candidate.entry.seconds,
                length_bars: candidate.length_bars,
              },
              ["family", "exit", "entry", "length_bars"],
            )
          }
        >
          Use this
        </button>
      </footer>
    </article>
  );
}

function Rejected({ items }: { items: RejectedCandidate[] }) {
  if (items.length === 0) return null;
  const reasons = new Map<string, number>();
  for (const item of items) reasons.set(item.reason, (reasons.get(item.reason) ?? 0) + 1);
  return (
    <details className="rejected">
      <summary>Rejected by constraints ({items.length})</summary>
      <ul>
        {[...reasons.entries()]
          .sort((a, b) => b[1] - a[1])
          .map(([reason, count]) => (
            <li key={reason}>
              <b>{count}×</b> {reason}
            </li>
          ))}
      </ul>
    </details>
  );
}

export function Candidates() {
  const { state } = useStore();
  const doc = currentDoc(state);
  const transition = doc ? transitionOf(doc) : null;
  const candidates = [...(transition?.candidates ?? [])].sort((a, b) => b.score - a.score);
  return (
    <section className="panel candidates" aria-label="Candidates">
      <h2>Candidates</h2>
      <PlanOptions />
      {!transition ? (
        <p className="empty">
          Load a track on each deck, then plan the mix. The planner proposes transitions with a
          score breakdown; each one is verified (loudness, peak, drift, clicks) before it is
          offered.
        </p>
      ) : (
        <>
          <AuditionBar />
          {transition.explanation?.chosen_because && (
            <p className="explain">{transition.explanation.chosen_because}</p>
          )}
          <div className="cards">
            {candidates.length === 0 && <p className="empty">This version lists no candidates.</p>}
            {candidates.map((c, i) => (
              <Card
                key={c.id}
                candidate={c}
                transition={transition}
                report={state.report}
                rank={i + 1}
              />
            ))}
          </div>
          <Rejected items={transition.explanation?.rejected_candidates ?? []} />
        </>
      )}
    </section>
  );
}
