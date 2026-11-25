import type { CandidateSummary } from "@mixconsole/schema-ts";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { api } from "../api/client";
import { fmtNum, fmtTime } from "../lib/format";
import { type View, xToTime } from "../lib/lanes";
import { barSeconds, moveCue, transitionOf } from "../lib/mixscript";
import { deckControls } from "../lib/registry";
import { gridLevel, gridText, stepTime } from "../lib/snap";
import { currentDoc, type DeckId } from "../state";
import { useStore } from "../store";
import { Intake } from "./Intake";
import { LaneCanvas } from "./LaneCanvas";

const WAVE_HEIGHT = 84;
const COLORS = {
  a: { wave: "#2a7f77", progress: "#56d4c8" },
  b: { wave: "#a8742c", progress: "#f6ad55" },
} as const;

export function Deck({ deck }: { deck: DeckId }) {
  const { state } = useStore();
  const track = state.tracks[deck];
  const lanes = state.lanes[deck];
  const peaks = state.peaks[deck];
  const letter = deck.toUpperCase();
  const busyAnalyzing = state.job?.kind === "analyze" && state.job.state !== "done";

  if (!track) {
    return (
      <section className={`deck deck-${deck}`} aria-label={`Deck ${letter}`}>
        <Intake deck={deck} />
      </section>
    );
  }
  return (
    <section
      className={`deck deck-${deck}${state.activeDeck === deck ? " active" : ""}`}
      aria-label={`Deck ${letter}`}
    >
      {lanes && peaks ? (
        <DeckBody key={`${track.hash}`} deck={deck} />
      ) : (
        <div className="deck-wait" role="status">
          <span className="deck-chip">{letter}</span> {track.name}:{" "}
          {busyAnalyzing
            ? `analysing… ${Math.round((state.job?.fraction ?? 0) * 100)}%`
            : "waiting for analysis"}
        </div>
      )}
    </section>
  );
}

function DeckBody({ deck }: { deck: DeckId }) {
  const { state, dispatch, actions } = useStore();
  const letter = deck.toUpperCase();
  const track = state.tracks[deck];
  const lanes = state.lanes[deck];
  const peaks = state.peaks[deck];
  const project = state.project;
  const container = useRef<HTMLDivElement>(null);
  const waveRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);
  const [width, setWidth] = useState(0);
  const [view, setView] = useState<View>({ start: 0, end: lanes?.duration ?? 1 });
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [ready, setReady] = useState(false);

  const syncView = useCallback(() => {
    const ws = wsRef.current;
    const total = lanes?.duration ?? 0;
    if (!ws || !total) return;
    const wrapper = ws.getWrapper();
    const pps = wrapper.scrollWidth / total;
    if (!(pps > 0)) return;
    const start = ws.getScroll() / pps;
    setView({ start, end: Math.min(total, start + ws.getWidth() / pps) || total });
  }, [lanes?.duration]);

  useEffect(() => {
    const el = container.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      setWidth(el.clientWidth);
      syncView();
    });
    observer.observe(el);
    setWidth(el.clientWidth);
    return () => observer.disconnect();
  }, [syncView]);

  useEffect(() => {
    if (!waveRef.current || !peaks || !track || !project || !lanes) return;
    const scale = 1 << ((peaks.bits ?? 8) - 1);
    const colors = COLORS[deck];
    const ws = WaveSurfer.create({
      container: waveRef.current,
      height: WAVE_HEIGHT,
      waveColor: colors.wave,
      progressColor: colors.progress,
      cursorColor: "#ffffff",
      cursorWidth: 1,
      normalize: false,
      minPxPerSec: 1,
      autoScroll: true,
      autoCenter: true,
      hideScrollbar: false,
      dragToSeek: true,
    });
    wsRef.current = ws;
    const peakData = Float32Array.from(peaks.data, (v) => v / scale);
    ws.on("ready", () => {
      setReady(true);
      syncView();
    });
    ws.on("scroll", syncView);
    ws.on("zoom", syncView);
    ws.on("redraw", syncView);
    ws.on("timeupdate", (t) => setTime(t));
    ws.on("play", () => setPlaying(true));
    ws.on("pause", () => setPlaying(false));
    ws.on("finish", () => setPlaying(false));
    ws.load(api.previewUrl(project.id, track.hash), [peakData], lanes.duration).catch(() => {
      /* a failed preview leaves the waveform and lanes usable; transport is disabled */
    });
    deckControls[deck] = {
      toggle: () => void ws.playPause(),
      zoom: (factor) => {
        const total = lanes.duration;
        const current = (ws.getWrapper().scrollWidth / total) * factor;
        const fit = ws.getWidth() / total;
        ws.zoom(Math.min(400, Math.max(fit, current)));
        syncView();
      },
      fit: () => {
        ws.zoom(1);
        syncView();
      },
      seek: (seconds) => ws.setTime(Math.max(0, Math.min(lanes.duration, seconds))),
    };
    return () => {
      delete deckControls[deck];
      ws.destroy();
      wsRef.current = null;
      setReady(false);
      setPlaying(false);
    };
  }, [peaks, track, project, lanes, deck, syncView]);

  if (!track || !lanes) return null;
  const doc = currentDoc(state);
  const transition = doc ? transitionOf(doc) : null;
  const cueKind = deck === "a" ? "exit" : "entry";
  const cue = transition ? transition[cueKind] : null;
  const regionSeconds = transition ? transition.length_bars * barSeconds(transition) : 0;

  return (
    <>
      <header className="deck-head">
        <span className="deck-chip">{letter}</span>
        <h2 className="deck-name" title={track.path}>
          {track.name}
        </h2>
        <dl className="deck-meta">
          <div>
            <dt>BPM</dt>
            <dd>{fmtNum(lanes.bpm ?? track.bpm, 1)}</dd>
          </div>
          <div>
            <dt>Key</dt>
            <dd>{track.camelot ?? "n/a"}</dd>
          </div>
          <div>
            <dt>Length</dt>
            <dd>{fmtTime(lanes.duration)}</dd>
          </div>
          <div>
            <dt>Vocals</dt>
            <dd>{lanes.vocals.length ? lanes.vocals.length : "none"}</dd>
          </div>
        </dl>
        <div className="deck-actions">
          <output className="timecode" aria-label={`Deck ${letter} position`}>
            {fmtTime(time)}
          </output>
          <button
            type="button"
            className="btn primary"
            disabled={!ready}
            aria-label={`${playing ? "Pause" : "Play"} deck ${letter}`}
            onClick={() => deckControls[deck]?.toggle()}
          >
            {playing ? "Pause" : "Play"}
          </button>
          {cue && (
            <button
              type="button"
              className="btn"
              disabled={!ready}
              onClick={() => {
                deckControls[deck]?.seek(Math.max(0, cue.seconds - 8));
                void wsRef.current?.play();
              }}
            >
              Play to {cueKind} cue
            </button>
          )}
          <button
            type="button"
            className="btn icon"
            aria-label={`Zoom out deck ${letter}`}
            onClick={() => deckControls[deck]?.zoom(1 / 1.6)}
          >
            −
          </button>
          <button
            type="button"
            className="btn icon"
            aria-label={`Zoom in deck ${letter}`}
            onClick={() => deckControls[deck]?.zoom(1.6)}
          >
            +
          </button>
          <button
            type="button"
            className="btn"
            aria-label={`Fit deck ${letter} to window`}
            onClick={() => deckControls[deck]?.fit()}
          >
            Fit
          </button>
          <button type="button" className="btn ghost" onClick={() => actions.clearDeck(deck)}>
            Replace
          </button>
        </div>
      </header>
      <div
        className="deck-body"
        ref={container}
        onPointerDown={() => dispatch({ type: "active-deck", deck })}
      >
        <div ref={waveRef} className="wave" style={{ height: WAVE_HEIGHT }} />
        {width > 0 && <LaneCanvas lanes={lanes} view={view} width={width} deck={deck} />}
        {transition && cue && (
          <CueLayer
            deck={deck}
            width={width}
            view={view}
            cueSeconds={cue.seconds}
            regionSeconds={regionSeconds}
            candidates={transition.candidates ?? []}
          />
        )}
      </div>
    </>
  );
}

interface CueLayerProps {
  deck: DeckId;
  width: number;
  view: View;
  cueSeconds: number;
  regionSeconds: number;
  candidates: CandidateSummary[];
}

function CueLayer({ deck, width, view, cueSeconds, regionSeconds, candidates }: CueLayerProps) {
  const { state, dispatch, actions } = useStore();
  const lanes = state.lanes[deck];
  const layer = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);
  const kind = deck === "a" ? "exit" : "entry";
  const letter = deck.toUpperCase();
  const span = view.end - view.start;
  const left = ((cueSeconds - view.start) / span) * width;
  const regionRight = ((cueSeconds + regionSeconds - view.start) / span) * width;
  const nudgeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selected = state.selection.cue === kind;

  const ghosts = useMemo(
    () =>
      candidates.map((c) => ({
        id: c.id,
        seconds: (deck === "a" ? c.exit : c.entry).seconds,
        family: c.family,
      })),
    [candidates, deck],
  );

  if (!lanes) return null;
  const doc = currentDoc(state);

  function liveMove(clientX: number, free: boolean): void {
    const rect = layer.current?.getBoundingClientRect();
    const current = currentDoc(state);
    if (!rect || !lanes || !current) return;
    const seconds = xToTime(clientX - rect.left, view, rect.width);
    dispatch({
      type: "draft",
      doc: moveCue(current, kind, seconds, lanes, free ? "off" : state.options.snap),
    });
  }

  function commitDraft(): void {
    const draft = state.draft;
    if (draft) void actions.commitDraft(`move ${kind} cue`);
  }

  function nudge(direction: 1 | -1, grid: "beat" | "downbeat" | "phrase"): void {
    const current = currentDoc(state);
    if (!current || !lanes) return;
    const seconds = transitionOf(current)[kind].seconds;
    const target = stepTime(seconds, lanes, grid, direction);
    dispatch({ type: "draft", doc: moveCue(current, kind, target, lanes, "off") });
    if (nudgeTimer.current) clearTimeout(nudgeTimer.current);
    nudgeTimer.current = setTimeout(() => {
      dispatch({ type: "select", patch: { cue: kind } });
      void actions.commitDraft(`nudge ${kind} cue`);
    }, 500);
  }

  const level = doc && lanes ? gridLevel(cueSeconds, lanes) : null;

  return (
    <div className="cue-layer" ref={layer} aria-label={`${kind} cue editing layer, deck ${letter}`}>
      {regionRight > 0 && left < width && regionSeconds > 0 && (
        <div
          className={`transition-region deck-${deck}`}
          style={{
            left: Math.max(0, left),
            width: Math.max(2, Math.min(width, regionRight) - Math.max(0, left)),
          }}
        />
      )}
      {ghosts.map((g) => {
        const x = ((g.seconds - view.start) / span) * width;
        if (x < 0 || x > width) return null;
        return (
          <button
            type="button"
            key={g.id}
            className={`ghost-cue${state.selection.candidateId === g.id ? " on" : ""}`}
            style={{ left: x }}
            title={`Candidate ${g.id} (${g.family})`}
            aria-label={`Select candidate ${g.id}, ${kind} at ${fmtTime(g.seconds)}`}
            onClick={() => dispatch({ type: "select", patch: { candidateId: g.id } })}
          />
        );
      })}
      {left >= -8 && left <= width + 8 && (
        <div
          className={`cue deck-${deck}${dragging ? " dragging" : ""}${selected ? " selected" : ""}`}
          style={{ left }}
        >
          <div
            className="cue-flag"
            role="slider"
            tabIndex={0}
            aria-label={`${kind === "exit" ? "Exit" : "Entry"} cue, deck ${letter}`}
            aria-valuemin={0}
            aria-valuemax={Math.round(lanes.duration * 10) / 10}
            aria-valuenow={Math.round(cueSeconds * 100) / 100}
            aria-valuetext={`${fmtTime(cueSeconds)}, ${gridText(level)}`}
            data-testid={`cue-${kind}`}
            onFocus={() => dispatch({ type: "select", patch: { cue: kind } })}
            onKeyDown={(event) => {
              const step = { ArrowLeft: -1, ArrowRight: 1 }[event.key] as 1 | -1 | undefined;
              if (step) {
                event.preventDefault();
                nudge(step, event.shiftKey ? "downbeat" : "beat");
              } else if (event.key === "PageUp" || event.key === "PageDown") {
                event.preventDefault();
                nudge(event.key === "PageDown" ? 1 : -1, "phrase");
              }
            }}
            onPointerDown={(event) => {
              if (!doc) return;
              event.currentTarget.setPointerCapture(event.pointerId);
              setDragging(true);
              dispatch({ type: "select", patch: { cue: kind } });
              dispatch({ type: "active-deck", deck });
            }}
            onPointerMove={(event) => {
              if (dragging) liveMove(event.clientX, event.altKey);
            }}
            onPointerUp={(event) => {
              event.currentTarget.releasePointerCapture(event.pointerId);
              setDragging(false);
              commitDraft();
            }}
            onPointerCancel={() => {
              setDragging(false);
              dispatch({ type: "draft", doc: null });
            }}
          >
            {kind === "exit" ? "EXIT" : "ENTRY"}
            <span className="cue-time">{fmtTime(cueSeconds)}</span>
          </div>
          <div className="cue-line" />
        </div>
      )}
    </div>
  );
}
