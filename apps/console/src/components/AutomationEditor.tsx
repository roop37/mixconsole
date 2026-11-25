import type { AutomationLane, AutomationPoint } from "@mixconsole/schema-ts";
import { useEffect, useRef, useState } from "react";
import { formatParam, sampleCurve, unitToValue, valueToUnit } from "../lib/automation";
import {
  addPoint,
  isLocked,
  laneLabel,
  movePoint,
  PARAM_RANGES,
  removePoint,
  setCurve,
  toggleLock,
  transitionOf,
} from "../lib/mixscript";
import { currentDoc } from "../state";
import { useStore } from "../store";

const HEIGHT = 170;
const PAD = { left: 52, right: 14, top: 12, bottom: 22 };
const CURVES: NonNullable<AutomationPoint["curve"]>[] = [
  "linear",
  "equal_power",
  "exponential",
  "step",
];

export function AutomationEditor() {
  const { state, dispatch, actions } = useStore();
  const doc = currentDoc(state);
  const transition = doc ? transitionOf(doc) : null;
  const lanes = transition?.automation ?? [];
  const selectedId = state.selection.laneId ?? lanes[0]?.id ?? null;
  const lane = lanes.find((l) => l.id === selectedId) ?? lanes[0] ?? null;

  if (!transition || !doc) {
    return (
      <section className="panel automation" aria-label="Automation">
        <h2>Automation</h2>
        <p className="empty">Plan a mix to edit its gain, EQ and filter curves.</p>
      </section>
    );
  }
  return (
    <section className="panel automation" aria-label="Automation">
      <h2>Automation</h2>
      {lanes.length === 0 ? (
        <p className="empty">
          This transition ({transition.family.replaceAll("_", " ")}) has no automation lanes.
        </p>
      ) : (
        <>
          <div role="tablist" aria-label="Automation lanes" className="lane-tabs">
            {lanes.map((l) => {
              const locked = isLocked(transition, l.id);
              return (
                <button
                  type="button"
                  key={l.id}
                  role="tab"
                  aria-selected={lane?.id === l.id}
                  className={`tab${lane?.id === l.id ? " on" : ""}`}
                  onClick={() => dispatch({ type: "select", patch: { laneId: l.id } })}
                >
                  {laneLabel(l)}
                  {locked && <span aria-label="locked"> ●</span>}
                </button>
              );
            })}
          </div>
          {lane && (
            <LaneEditor
              key={lane.id}
              lane={lane}
              totalBeats={transition.length_bars * (transition.beats_per_bar ?? 4)}
              beatsPerBar={transition.beats_per_bar ?? 4}
              locked={isLocked(transition, lane.id)}
              onToggleLock={() =>
                void actions.commitEdit(toggleLock(doc, lane.id), `toggle lock ${lane.id}`)
              }
            />
          )}
        </>
      )}
    </section>
  );
}

interface LaneProps {
  lane: AutomationLane;
  totalBeats: number;
  beatsPerBar: number;
  locked: boolean;
  onToggleLock(): void;
}

function LaneEditor({ lane, totalBeats, beatsPerBar, locked, onToggleLock }: LaneProps) {
  const { state, dispatch, actions } = useStore();
  const wrap = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(600);
  const [picked, setPicked] = useState<number | null>(null);
  const [drag, setDrag] = useState<number | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const range = PARAM_RANGES[lane.parameter];
  const beats = Math.max(totalBeats, lane.points[lane.points.length - 1]?.beat ?? 1, 1);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(Math.max(240, el.clientWidth)));
    observer.observe(el);
    setWidth(Math.max(240, el.clientWidth));
    return () => observer.disconnect();
  }, []);

  const innerW = width - PAD.left - PAD.right;
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const bx = (beat: number) => PAD.left + (beat / beats) * innerW;
  const vy = (value: number) => PAD.top + (1 - valueToUnit(value, range)) * innerH;
  const doc = currentDoc(state);

  function pointer(event: { clientX: number; clientY: number }): { beat: number; value: number } {
    const rect = wrap.current?.getBoundingClientRect();
    const left = rect?.left ?? 0;
    const top = rect?.top ?? 0;
    const beat = ((event.clientX - left - PAD.left) / innerW) * beats;
    const value = unitToValue(1 - (event.clientY - top - PAD.top) / innerH, range);
    return { beat: Math.min(beats, Math.max(0, beat)), value };
  }

  function live(index: number, beat: number, value: number, free: boolean): void {
    if (!doc) return;
    dispatch({
      type: "draft",
      doc: movePoint(doc, lane.id, index, free ? beat : Math.round(beat * 4) / 4, value),
    });
  }

  function scheduleCommit(): void {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void actions.commitDraft(`edit ${lane.id}`), 600);
  }

  const curve = sampleCurve(lane.points, beats);
  const path = curve
    .map(([b, v], i) => `${i === 0 ? "M" : "L"}${bx(b).toFixed(1)},${vy(v).toFixed(1)}`)
    .join(" ");
  const selected = picked !== null ? lane.points[picked] : undefined;
  const bars = Math.floor(beats / beatsPerBar);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((u) => unitToValue(u, range));

  return (
    <div className="lane-editor">
      <div className="lane-bar">
        <button
          type="button"
          className="btn"
          aria-pressed={locked}
          onClick={onToggleLock}
          title="A locked lane is kept when the mix is re-planned"
        >
          {locked ? "Locked" : "Lock lane"}
        </button>
        <label>
          Curve of selected point
          <select
            className="input"
            disabled={picked === null}
            value={selected?.curve ?? "linear"}
            onChange={(e) =>
              doc &&
              picked !== null &&
              void actions.commitEdit(
                setCurve(doc, lane.id, picked, e.target.value as (typeof CURVES)[number]),
                `curve ${lane.id}`,
              )
            }
          >
            {CURVES.map((c) => (
              <option key={c} value={c}>
                {c.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <span className="muted">
          Drag points. Double-click adds one; Delete removes the selected point. Arrow keys nudge.
        </span>
      </div>
      <div ref={wrap} className="lane-svg-wrap">
        <svg
          width={width}
          height={HEIGHT}
          role="group"
          aria-label={`${laneLabel(lane)} automation, ${lane.points.length} points`}
          onDoubleClick={(event) => {
            if (!doc) return;
            const { beat, value } = pointer(event);
            void actions.commitEdit(
              addPoint(doc, lane.id, Math.round(beat * 4) / 4, value),
              `add point ${lane.id}`,
            );
          }}
        >
          <rect x={PAD.left} y={PAD.top} width={innerW} height={innerH} className="plot" />
          {ticks.map((t) => (
            <g key={t}>
              <line x1={PAD.left} x2={PAD.left + innerW} y1={vy(t)} y2={vy(t)} className="grid" />
              <text x={PAD.left - 6} y={vy(t) + 3} textAnchor="end" className="axis">
                {formatParam(t, range)}
              </text>
            </g>
          ))}
          {Array.from({ length: bars + 1 }, (_, i) => i * beatsPerBar).map((b) => (
            <g key={b}>
              <line x1={bx(b)} x2={bx(b)} y1={PAD.top} y2={PAD.top + innerH} className="grid v" />
              <text x={bx(b)} y={HEIGHT - 6} textAnchor="middle" className="axis">
                {b / beatsPerBar}
              </text>
            </g>
          ))}
          <path d={path} className="curve" />
          {lane.points.map((p, i) => (
            <circle
              // biome-ignore lint/suspicious/noArrayIndexKey: points have no ids; order is the identity
              key={i}
              cx={bx(p.beat)}
              cy={vy(p.value)}
              r={picked === i || drag === i ? 7 : 5.5}
              className={`pt${picked === i ? " on" : ""}`}
              tabIndex={0}
              role="slider"
              aria-label={`Point ${i + 1} of ${lane.points.length}`}
              aria-valuenow={Math.round(p.value * 100) / 100}
              aria-valuetext={`beat ${p.beat}, ${formatParam(p.value, range)}`}
              onFocus={() => setPicked(i)}
              onPointerDown={(event) => {
                event.stopPropagation();
                event.currentTarget.setPointerCapture(event.pointerId);
                setPicked(i);
                setDrag(i);
              }}
              onPointerMove={(event) => {
                if (drag !== i) return;
                const { beat, value } = pointer(event);
                live(i, beat, value, event.altKey);
              }}
              onPointerUp={(event) => {
                event.currentTarget.releasePointerCapture(event.pointerId);
                setDrag(null);
                void actions.commitDraft(`edit ${lane.id}`);
              }}
              onKeyDown={(event) => {
                if (!doc) return;
                const base = state.draft ? lane.points[i] : p;
                if (!base) return;
                const fine = event.shiftKey ? 4 : 1;
                const unit = valueToUnit(base.value, range);
                const moves: Record<string, [number, number]> = {
                  ArrowLeft: [-0.25 * fine, 0],
                  ArrowRight: [0.25 * fine, 0],
                  ArrowUp: [0, 0.02 * fine],
                  ArrowDown: [0, -0.02 * fine],
                };
                const move = moves[event.key];
                if (move) {
                  event.preventDefault();
                  live(i, base.beat + move[0], unitToValue(unit + move[1], range), true);
                  scheduleCommit();
                } else if (event.key === "Delete" || event.key === "Backspace") {
                  event.preventDefault();
                  void actions.commitEdit(removePoint(doc, lane.id, i), `remove point ${lane.id}`);
                  setPicked(null);
                }
              }}
            />
          ))}
        </svg>
      </div>
    </div>
  );
}
