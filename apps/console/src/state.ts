import type {
  Job,
  JobEvent,
  Lanes,
  MixScript,
  MixScriptDocument,
  MixScriptVersion,
  Peaks,
  ProjectInfo,
  RenderRecord,
  TrackRecord,
} from "@mixconsole/schema-ts";
import { commit, emptyHistory, type History, redo, undo } from "./lib/history";
import { asMixScript } from "./lib/mixscript";
import type { Report } from "./lib/report";
import type { SnapMode } from "./lib/snap";

export type DeckId = "a" | "b";
export const DECKS: DeckId[] = ["a", "b"];
export type View = "console" | "library" | "listen";
export type Stems = "off" | "auto" | "on";
export type Style = "auto" | "smooth" | "club";

export interface JobView {
  id: string;
  kind: string;
  label: string;
  stage: string;
  fraction: number;
  message: string;
  state: Job["state"];
}

export interface Options {
  style: Style;
  candidates: number;
  stems: Stems;
  snap: SnapMode;
}

export interface Notice {
  kind: "error" | "info";
  text: string;
}

export interface AppState {
  ready: boolean;
  view: View;
  activeDeck: DeckId;
  project: ProjectInfo | null;
  projects: ProjectInfo[];
  tracks: Record<DeckId, TrackRecord | null>;
  uploading: Record<DeckId, string | null>;
  lanes: Record<DeckId, Lanes | null>;
  peaks: Record<DeckId, Peaks | null>;
  versions: Record<string, MixScriptDocument>;
  versionList: MixScriptVersion[];
  history: History;
  /** Uncommitted live edit (a cue or automation point being dragged). */
  draft: MixScript | null;
  renders: RenderRecord[];
  /** The "mix" job render that produced candidate previews, and its verification report. */
  planRenderId: string | null;
  report: Report | null;
  job: JobView | null;
  options: Options;
  selection: { cue: "exit" | "entry" | null; candidateId: string | null; laneId: string | null };
  notice: Notice | null;
}

const none: Record<DeckId, null> = { a: null, b: null };

export function initialState(): AppState {
  return {
    ready: false,
    view: "console",
    activeDeck: "a",
    project: null,
    projects: [],
    tracks: { ...none },
    uploading: { ...none },
    lanes: { ...none },
    peaks: { ...none },
    versions: {},
    versionList: [],
    history: emptyHistory,
    draft: null,
    renders: [],
    planRenderId: null,
    report: null,
    job: null,
    options: { style: "auto", candidates: 4, stems: "off", snap: "phrase" },
    selection: { cue: null, candidateId: null, laneId: null },
    notice: null,
  };
}

export type Action =
  | { type: "ready"; projects: ProjectInfo[] }
  | { type: "project"; project: ProjectInfo; projects?: ProjectInfo[] }
  | { type: "reset-session" }
  | { type: "view"; view: View }
  | { type: "active-deck"; deck: DeckId }
  | { type: "clear-plan" }
  | { type: "track"; deck: DeckId; track: TrackRecord | null }
  | { type: "uploading"; deck: DeckId; name: string | null }
  | { type: "deck-data"; deck: DeckId; lanes: Lanes; peaks: Peaks }
  | { type: "job-start"; job: Job; label: string }
  | { type: "job-progress"; event: JobEvent }
  | { type: "job-end"; job: Job }
  | { type: "job-clear"; id: string }
  | { type: "options"; patch: Partial<Options> }
  | { type: "select"; patch: Partial<AppState["selection"]> }
  | { type: "version-loaded"; doc: MixScriptDocument }
  | { type: "versions"; list: MixScriptVersion[] }
  | { type: "commit"; id: string }
  | { type: "undo" }
  | { type: "redo" }
  | { type: "draft"; doc: MixScript | null }
  | { type: "renders"; renders: RenderRecord[] }
  | { type: "plan-render"; renderId: string | null; report: Report | null }
  | { type: "notice"; notice: Notice | null };

export function currentId(state: AppState): string | null {
  return state.history.current;
}

/** The document on screen: a live draft while dragging, else the current saved version. */
export function currentDoc(state: AppState): MixScript | null {
  if (state.draft) return state.draft;
  const id = state.history.current;
  const stored = id ? state.versions[id] : undefined;
  return stored ? asMixScript(stored.document) : null;
}

export function renderFor(
  state: AppState,
  audio: "wav" | "flac" | "any" = "any",
): RenderRecord | null {
  const id = state.history.current;
  const matches = state.renders.filter(
    (r) => r.mixscript_id === id && (audio === "any" || r.audio.endsWith(`.${audio}`)),
  );
  return matches[matches.length - 1] ?? null;
}

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case "ready":
      return { ...state, ready: true, projects: action.projects };
    case "project":
      return {
        ...state,
        project: action.project,
        projects: action.projects ?? state.projects,
      };
    case "reset-session":
      return {
        ...initialState(),
        ready: true,
        project: state.project,
        projects: state.projects,
        options: state.options,
        view: state.view,
      };
    case "view":
      return { ...state, view: action.view };
    case "active-deck":
      return { ...state, activeDeck: action.deck };
    case "clear-plan":
      return {
        ...state,
        versions: {},
        versionList: [],
        history: emptyHistory,
        draft: null,
        renders: [],
        planRenderId: null,
        report: null,
        selection: { cue: null, candidateId: null, laneId: null },
      };
    case "track":
      return {
        ...state,
        tracks: { ...state.tracks, [action.deck]: action.track },
        lanes: action.track ? state.lanes : { ...state.lanes, [action.deck]: null },
        peaks: action.track ? state.peaks : { ...state.peaks, [action.deck]: null },
        uploading: { ...state.uploading, [action.deck]: null },
      };
    case "uploading":
      return { ...state, uploading: { ...state.uploading, [action.deck]: action.name } };
    case "deck-data":
      return {
        ...state,
        lanes: { ...state.lanes, [action.deck]: action.lanes },
        peaks: { ...state.peaks, [action.deck]: action.peaks },
      };
    case "job-start":
      return {
        ...state,
        job: {
          id: action.job.id,
          kind: action.job.kind,
          label: action.label,
          stage: action.job.stage,
          fraction: action.job.fraction,
          message: action.job.message,
          state: action.job.state,
        },
      };
    case "job-progress":
      if (!state.job) return state;
      return {
        ...state,
        job: {
          ...state.job,
          stage: action.event.stage,
          fraction: Math.max(state.job.fraction, action.event.fraction),
          message: action.event.message,
          state: "running",
        },
      };
    case "job-end":
      if (!state.job || state.job.id !== action.job.id) return state;
      return {
        ...state,
        job: {
          ...state.job,
          state: action.job.state,
          fraction: action.job.state === "done" ? 1 : state.job.fraction,
          stage: action.job.stage,
          message: action.job.error ?? action.job.message,
        },
      };
    case "job-clear":
      return state.job?.id === action.id && state.job.state !== "running"
        ? { ...state, job: null }
        : state;
    case "options":
      return { ...state, options: { ...state.options, ...action.patch } };
    case "select":
      return { ...state, selection: { ...state.selection, ...action.patch } };
    case "version-loaded":
      return { ...state, versions: { ...state.versions, [action.doc.id]: action.doc } };
    case "versions":
      return { ...state, versionList: action.list };
    case "commit":
      return { ...state, history: commit(state.history, action.id), draft: null };
    case "undo":
      return { ...state, history: undo(state.history), draft: null };
    case "redo":
      return { ...state, history: redo(state.history), draft: null };
    case "draft":
      return { ...state, draft: action.doc };
    case "renders":
      return { ...state, renders: action.renders };
    case "plan-render":
      return { ...state, planRenderId: action.renderId, report: action.report };
    case "notice":
      return { ...state, notice: action.notice };
  }
}
