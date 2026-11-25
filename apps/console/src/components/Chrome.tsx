import { useEffect, useRef } from "react";
import { fmtNum } from "../lib/format";
import type { View } from "../state";
import { useStore } from "../store";

const VIEWS: { id: View; label: string; key: string }[] = [
  { id: "console", label: "Console", key: "Alt+1" },
  { id: "library", label: "Library", key: "Alt+2" },
  { id: "listen", label: "Listen", key: "Alt+3" },
];

export const SHORTCUTS: [string, string][] = [
  ["Space", "Play / pause the active deck"],
  ["1 / 2", "Select deck A / B"],
  ["+ / − / 0", "Zoom the active deck in / out / fit"],
  ["P", "Plan the mix (plan, verify, render)"],
  ["R", "Re-render the current version"],
  ["A / B", "Switch the audition slot (position kept relative to the handoff)"],
  ["Enter", "Play / pause the audition"],
  ["← →  (on a cue flag)", "Move the cue one beat; Shift = one bar; PageUp/PageDown = one phrase"],
  ["Alt + drag", "Move a cue or point without snapping"],
  ["Ctrl/Cmd + Z", "Undo (previous MixScript version)"],
  ["Ctrl/Cmd + Shift + Z", "Redo"],
  ["Alt + 1 / 2 / 3", "Console / Library / Listen"],
  ["?", "This help"],
];

export function Header() {
  const { state, dispatch, actions } = useStore();
  return (
    <header className="app-header">
      <h1 className="brand">
        <span aria-hidden="true" className="brand-mark" />
        MixConsole
      </h1>
      <nav aria-label="Views" className="views" role="tablist">
        {VIEWS.map((v) => (
          <button
            type="button"
            key={v.id}
            role="tab"
            aria-selected={state.view === v.id}
            aria-keyshortcuts={v.key}
            className={`tab${state.view === v.id ? " on" : ""}`}
            onClick={() => dispatch({ type: "view", view: v.id })}
          >
            {v.label}
          </button>
        ))}
      </nav>
      <div className="session">
        <label htmlFor="session">Session</label>
        <select
          id="session"
          className="input"
          value={state.project?.id ?? ""}
          onChange={(e) => void actions.loadProject(e.target.value)}
        >
          {state.projects.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.tracks} tracks)
            </option>
          ))}
          {state.project && !state.projects.some((p) => p.id === state.project?.id) && (
            <option value={state.project.id}>{state.project.name}</option>
          )}
        </select>
        <button type="button" className="btn" onClick={() => void actions.newSession()}>
          New session
        </button>
      </div>
      <button
        type="button"
        className="btn ghost"
        aria-haspopup="dialog"
        aria-keyshortcuts="?"
        onClick={() => document.getElementById("help")?.dispatchEvent(new Event("open"))}
      >
        Shortcuts
      </button>
    </header>
  );
}

export function JobBar() {
  const { state, actions } = useStore();
  const job = state.job;
  const active = job?.state === "running" || job?.state === "queued";
  return (
    <footer className="jobbar" aria-label="Background work">
      {job ? (
        <>
          <span
            className={`chip chip-${job.state === "failed" ? "failed" : job.state === "done" ? "passed" : "unverified"}`}
          >
            {job.state}
          </span>
          <strong>{job.label}</strong>
          <span className="stage">{job.stage}</span>
          <progress
            max={1}
            value={job.fraction}
            aria-label={`${job.label} progress`}
            aria-valuetext={`${Math.round(job.fraction * 100)} percent`}
          />
          <output className="pct">{fmtNum(job.fraction * 100, 0)}%</output>
          <span className="msg" title={job.message}>
            {job.message}
          </span>
          {active && (
            <button type="button" className="btn" onClick={() => void actions.cancelJob()}>
              Cancel
            </button>
          )}
        </>
      ) : (
        <span className="muted">
          Idle. Local only: this page talks to 127.0.0.1 and nothing else.
        </span>
      )}
    </footer>
  );
}

export function Notice() {
  const { state, actions } = useStore();
  const notice = state.notice;
  useEffect(() => {
    if (notice?.kind !== "info") return;
    const handle = setTimeout(() => actions.dismissNotice(), 6000);
    return () => clearTimeout(handle);
  }, [notice, actions]);
  if (!notice) return null;
  return (
    <div className={`notice ${notice.kind}`} role={notice.kind === "error" ? "alert" : "status"}>
      <span>{notice.text}</span>
      <button type="button" className="btn ghost" onClick={() => actions.dismissNotice()}>
        Dismiss
      </button>
    </div>
  );
}

export function Help() {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const open = () => el.showModal();
    el.addEventListener("open", open);
    return () => el.removeEventListener("open", open);
  }, []);
  return (
    <dialog id="help" ref={ref} className="help" aria-labelledby="help-title">
      <h2 id="help-title">Keyboard shortcuts</h2>
      <table>
        <tbody>
          {SHORTCUTS.map(([keys, what]) => (
            <tr key={keys}>
              <th scope="row">
                <kbd>{keys}</kbd>
              </th>
              <td>{what}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <form method="dialog">
        <button type="submit" className="btn primary">
          Close
        </button>
      </form>
    </dialog>
  );
}
