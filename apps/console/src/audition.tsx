import type { CandidateSummary } from "@mixconsole/schema-ts";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { api } from "./api/client";
import { familyLabel } from "./lib/format";
import { transitionOf } from "./lib/mixscript";
import { isTypingTarget } from "./lib/registry";
import { currentDoc, renderFor } from "./state";
import { useStore } from "./store";

export interface Source {
  key: string;
  label: string;
  url: string;
  /** Seconds into the file where the handoff starts. */
  seamAt: number;
}

export type Slot = "a" | "b";

/** Candidate previews are cut from 15 s before the seam (service.mix_pair). */
const PREVIEW_SEAM = 15;
export const LEAD_IN = 8;

interface AuditionApi {
  sources: Source[];
  slots: Record<Slot, string | null>;
  active: Slot;
  playing: boolean;
  /** Seconds relative to the seam of the active source (negative = before the handoff). */
  rel: number;
  setSlot(slot: Slot, key: string | null): void;
  playKey(key: string): void;
  toggle(): void;
  switchTo(slot: Slot): void;
  seekRel(rel: number): void;
}

const Context = createContext<AuditionApi | null>(null);

export function useAudition(): AuditionApi {
  const value = useContext(Context);
  if (!value) throw new Error("AuditionProvider missing");
  return value;
}

export function candidateSourceKey(candidate: CandidateSummary): string {
  return `cand:${candidate.id}`;
}

export function AuditionProvider({ children }: { children: ReactNode }) {
  const { state } = useStore();
  const project = state.project;
  const doc = currentDoc(state);
  const mixRender = renderFor(state);
  const planRender = state.planRenderId;

  const sources = useMemo<Source[]>(() => {
    if (!project || !doc) return [];
    const transition = transitionOf(doc);
    const list: Source[] = [];
    if (mixRender) {
      list.push({
        key: "mix",
        label: "Current mix (seam)",
        url: api.renderFileUrl(project.id, mixRender.id, mixRender.audio),
        seamAt: transition.exit.seconds,
      });
    }
    if (planRender) {
      for (const candidate of transition.candidates ?? []) {
        if (!candidate.preview_artifact) continue;
        list.push({
          key: candidateSourceKey(candidate),
          label: `${candidate.id} · ${familyLabel(candidate.family)}, ${candidate.length_bars} bars`,
          url: api.renderFileUrl(project.id, planRender, candidate.preview_artifact),
          seamAt: PREVIEW_SEAM,
        });
      }
    }
    return list;
  }, [project, doc, mixRender, planRender]);

  const [slots, setSlots] = useState<Record<Slot, string | null>>({ a: null, b: null });
  const [active, setActive] = useState<Slot>("a");
  const [playing, setPlaying] = useState(false);
  const [rel, setRel] = useState(-LEAD_IN);
  const elements = useRef<Record<Slot, HTMLAudioElement | null>>({ a: null, b: null });
  const sourcesRef = useRef(sources);
  sourcesRef.current = sources;
  const slotsRef = useRef(slots);
  slotsRef.current = slots;
  const activeRef = useRef(active);
  activeRef.current = active;

  const sourceOf = useCallback(
    (slot: Slot) => sourcesRef.current.find((s) => s.key === slotsRef.current[slot]) ?? null,
    [],
  );

  // keep the slots pointing at sources that still exist; default to the first two
  useEffect(() => {
    setSlots((previous) => {
      const keys = sources.map((s) => s.key);
      const valid = (k: string | null) => (k && keys.includes(k) ? k : null);
      const a = valid(previous.a) ?? keys[0] ?? null;
      const b = valid(previous.b) ?? keys.find((k) => k !== a) ?? null;
      return a === previous.a && b === previous.b ? previous : { a, b };
    });
  }, [sources]);

  useEffect(() => {
    const created: Record<Slot, HTMLAudioElement> = { a: new Audio(), b: new Audio() };
    for (const slot of ["a", "b"] as Slot[]) {
      const el = created[slot];
      el.preload = "auto";
      el.addEventListener("timeupdate", () => {
        const source = sourceOf(slot);
        if (activeRef.current === slot && source) setRel(el.currentTime - source.seamAt);
      });
      el.addEventListener("ended", () => setPlaying(false));
    }
    elements.current = created;
    return () => {
      for (const el of Object.values(created)) {
        el.pause();
        el.removeAttribute("src");
      }
      elements.current = { a: null, b: null };
    };
  }, [sourceOf]);

  // load the source of each slot
  useEffect(() => {
    for (const slot of ["a", "b"] as Slot[]) {
      const el = elements.current[slot];
      const source = sources.find((s) => s.key === slots[slot]);
      if (el && source && el.dataset.src !== source.url) {
        el.dataset.src = source.url;
        el.src = source.url;
        el.load();
      } else if (el && !source && el.dataset.src) {
        el.pause();
        el.removeAttribute("src");
        el.dataset.src = "";
      }
    }
  }, [slots, sources]);

  const seekRel = useCallback(
    (value: number) => {
      const el = elements.current[activeRef.current];
      const source = sourceOf(activeRef.current);
      if (el && source) el.currentTime = Math.max(0, source.seamAt + value);
      setRel(value);
    },
    [sourceOf],
  );

  const play = useCallback(
    (slot: Slot, at: number) => {
      const other: Slot = slot === "a" ? "b" : "a";
      elements.current[other]?.pause();
      const el = elements.current[slot];
      const source = sourceOf(slot);
      if (!el || !source) return;
      const start = () => {
        el.currentTime = Math.max(0, source.seamAt + at);
        void el.play().then(
          () => setPlaying(true),
          () => setPlaying(false),
        );
      };
      if (el.readyState >= 1) start();
      else el.addEventListener("loadedmetadata", start, { once: true });
      setActive(slot);
      setRel(at);
    },
    [sourceOf],
  );

  const api2: AuditionApi = useMemo(
    () => ({
      sources,
      slots,
      active,
      playing,
      rel,
      setSlot: (slot, key) => setSlots((previous) => ({ ...previous, [slot]: key })),
      playKey: (key) => {
        setSlots((previous) => ({ ...previous, a: key }));
        // the source loads on the next effect; play after it is attached
        setTimeout(() => play("a", -LEAD_IN), 0);
      },
      toggle: () => {
        const el = elements.current[activeRef.current];
        if (!el || !sourceOf(activeRef.current)) return;
        if (el.paused) play(activeRef.current, Math.max(-LEAD_IN, rel));
        else {
          el.pause();
          setPlaying(false);
        }
      },
      switchTo: (slot) => {
        const from = elements.current[activeRef.current];
        const source = sourceOf(activeRef.current);
        const position = from && source ? from.currentTime - source.seamAt : rel;
        const wasPlaying = from ? !from.paused : false;
        from?.pause();
        setActive(slot);
        activeRef.current = slot;
        if (wasPlaying) play(slot, position);
        else setRel(position);
      },
      seekRel,
    }),
    [sources, slots, active, playing, rel, play, seekRel, sourceOf],
  );

  // A / B switch and Enter play/pause, outside text fields
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target) || event.metaKey || event.ctrlKey || event.altKey) return;
      if (event.key === "a" || event.key === "b") api2.switchTo(event.key);
      else if (event.key === "Enter" && !(event.target instanceof HTMLButtonElement)) api2.toggle();
      else return;
      event.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [api2]);

  return <Context.Provider value={api2}>{children}</Context.Provider>;
}
