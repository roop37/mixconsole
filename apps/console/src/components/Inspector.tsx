import { useState } from "react";
import { FAMILIES, familyLabel, fmtNum, fmtTime } from "../lib/format";
import { canRedo, canUndo } from "../lib/history";
import { isLocked, type LockField, toggleLock, transitionOf } from "../lib/mixscript";
import { gridLevel, gridText, SNAP_MODES, type SnapMode } from "../lib/snap";
import { currentDoc, renderFor } from "../state";
import { useStore } from "../store";

const LENGTHS = [0, 1, 2, 4, 8, 16, 32];

function LockButton({ field, label }: { field: LockField; label: string }) {
  const { state, actions } = useStore();
  const doc = currentDoc(state);
  if (!doc) return null;
  const locked = isLocked(transitionOf(doc), field);
  return (
    <button
      type="button"
      className="btn lock"
      aria-pressed={locked}
      aria-label={`Lock ${label}`}
      title={
        locked ? `${label} is locked: a re-plan keeps it` : `Lock ${label} so a re-plan keeps it`
      }
      onClick={() =>
        void actions.commitEdit(toggleLock(doc, field), `${locked ? "unlock" : "lock"} ${field}`)
      }
    >
      {locked ? "Locked" : "Lock"}
    </button>
  );
}

export function Inspector() {
  const { state, dispatch, actions } = useStore();
  const doc = currentDoc(state);
  const transition = doc ? transitionOf(doc) : null;
  const busy = state.job?.state === "running" || state.job?.state === "queued";
  const current = state.versionList.find((v) => v.id === state.history.current);
  const render = renderFor(state);
  const [showVersions, setShowVersions] = useState(false);

  if (!transition) {
    return (
      <section className="panel inspector" aria-label="Edit transition">
        <h2>Edit</h2>
        <p className="empty">Nothing to edit yet.</p>
      </section>
    );
  }
  const lanesA = state.lanes.a;
  const lanesB = state.lanes.b;
  const gridOf = (kind: "exit" | "entry") => {
    const lanes = kind === "exit" ? lanesA : lanesB;
    return lanes ? gridLevel(transition[kind].seconds, lanes) : null;
  };
  return (
    <section className="panel inspector" aria-label="Edit transition">
      <h2>Edit</h2>
      <div className="toolbar">
        <button
          type="button"
          className="btn"
          disabled={!canUndo(state.history) || busy}
          aria-keyshortcuts="Control+Z Meta+Z"
          onClick={() => void actions.undo()}
        >
          Undo
        </button>
        <button
          type="button"
          className="btn"
          disabled={!canRedo(state.history) || busy}
          aria-keyshortcuts="Control+Shift+Z Meta+Shift+Z"
          onClick={() => void actions.redo()}
        >
          Redo
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => void actions.replan()}>
          Re-plan (keep locks)
        </button>
        <button
          type="button"
          className="btn primary"
          disabled={busy}
          aria-keyshortcuts="r"
          data-testid="rerender"
          onClick={() => void actions.render("wav")}
        >
          Re-render
        </button>
        <span
          className={`chip ${render ? "chip-passed" : "chip-unverified"}`}
          data-testid="render-status"
        >
          {render ? `Rendered (${render.id})` : "Render stale"}
        </span>
      </div>
      <div className="field-grid">
        <label htmlFor="family">Family</label>
        <div className="row">
          <select
            id="family"
            className="input"
            value={transition.family}
            disabled={busy}
            onChange={(e) => void actions.replan({ family: e.target.value }, ["family"])}
          >
            {FAMILIES.map((f) => (
              <option key={f} value={f}>
                {familyLabel(f)}
              </option>
            ))}
          </select>
          <LockButton field="family" label="family" />
        </div>
        <label htmlFor="length">Length</label>
        <div className="row">
          <select
            id="length"
            className="input"
            value={transition.length_bars}
            disabled={busy}
            onChange={(e) =>
              void actions.replan({ length_bars: Number(e.target.value) }, ["length_bars"])
            }
          >
            {LENGTHS.map((n) => (
              <option key={n} value={n}>
                {n} bars
              </option>
            ))}
          </select>
          <LockButton field="length_bars" label="length" />
        </div>
        <span className="label">Exit cue (A)</span>
        <div className="row">
          <output data-testid="exit-time">{fmtTime(transition.exit.seconds)}</output>
          <span className="muted">beat {fmtNum(transition.exit.beat, 1)}</span>
          <span className={`chip ${gridOf("exit") ? "chip-passed" : "chip-unverified"}`}>
            {gridText(gridOf("exit"))}
          </span>
          <LockButton field="exit" label="exit cue" />
        </div>
        <span className="label">Entry cue (B)</span>
        <div className="row">
          <output data-testid="entry-time">{fmtTime(transition.entry.seconds)}</output>
          <span className="muted">beat {fmtNum(transition.entry.beat, 1)}</span>
          <span className={`chip ${gridOf("entry") ? "chip-passed" : "chip-unverified"}`}>
            {gridText(gridOf("entry"))}
          </span>
          <LockButton field="entry" label="entry cue" />
        </div>
        <label htmlFor="snap">Cue snap</label>
        <select
          id="snap"
          className="input"
          value={state.options.snap}
          onChange={(e) =>
            dispatch({ type: "options", patch: { snap: e.target.value as SnapMode } })
          }
        >
          {SNAP_MODES.map((m) => (
            <option key={m} value={m}>
              {m === "off" ? "Off (free)" : m}
            </option>
          ))}
        </select>
      </div>
      <p className="muted small">
        Drag the EXIT/ENTRY flags on the decks (hold Alt to bypass snapping), or focus one and use ←
        → (beat), Shift+← → (bar), PageUp/PageDown (phrase). Moving a cue drops the per-beat warp
        map; the renderer then uses the constant tempo map.
      </p>
      <div className="versions">
        <button
          type="button"
          className="btn ghost"
          aria-expanded={showVersions}
          onClick={() => setShowVersions(!showVersions)}
        >
          Versions ({state.versionList.length}){current ? ` · now v${current.seq}` : ""}
        </button>
        {showVersions && (
          <ol className="version-list">
            {state.versionList.map((v) => (
              <li key={v.id} aria-current={v.id === state.history.current}>
                v{v.seq} · {v.label}{" "}
                {v.parent_id
                  ? `(from ${state.versionList.find((p) => p.id === v.parent_id)?.seq ?? "?"})`
                  : ""}
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

export function ExportPanel() {
  const { state, actions } = useStore();
  const doc = currentDoc(state);
  const busy = state.job?.state === "running" || state.job?.state === "queued";
  const report = actions.reportUrl();
  return (
    <section className="panel export" aria-label="Export">
      <h2>Export</h2>
      <div className="toolbar">
        <button
          type="button"
          className="btn primary"
          disabled={!doc || busy}
          onClick={() => void actions.exportAudio("wav")}
          data-testid="export-wav"
        >
          WAV
        </button>
        <button
          type="button"
          className="btn"
          disabled={!doc || busy}
          onClick={() => void actions.exportAudio("flac")}
          data-testid="export-flac"
        >
          FLAC
        </button>
        <button
          type="button"
          className="btn"
          disabled={!doc}
          onClick={() => actions.exportMixScript()}
          data-testid="export-mixscript"
        >
          MixScript
        </button>
        {report ? (
          <a className="btn" href={report} target="_blank" rel="noreferrer">
            Report
          </a>
        ) : (
          <button type="button" className="btn" disabled>
            Report
          </button>
        )}
      </div>
      <p className="muted small">
        Audio is rendered from the saved MixScript version on screen (deterministic: same input and
        MixScript, same bytes). Exports download through the browser.
      </p>
    </section>
  );
}
