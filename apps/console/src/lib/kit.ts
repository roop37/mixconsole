/**
 * Blind listening page support: reads the kit config that `mixconsole listen build` embeds in
 * index.html and writes votes in the `listen-votes/v1` JSON that `mixconsole listen results` reads.
 * The kit JSON is a local file format, validated here, not part of the HTTP API.
 */

export interface ABTrial {
  id: string;
  pair: string;
  title: string;
  left: string;
  right: string;
}
export interface MushraSet {
  pair: string;
  title: string;
  reference: string;
  items: string[];
}
export interface KitConfig {
  kit_id: string;
  ab: ABTrial[];
  mushra: MushraSet[];
  audio: Record<string, string>;
}
export interface ABVote {
  trial: string;
  pair: string;
  left: string;
  right: string;
  choice: "left" | "right" | "tie";
}
export interface MushraVote {
  pair: string;
  scores: Record<string, number>;
}
export interface VoteState {
  rater: string;
  ab: Record<string, ABVote>;
  mushra: Record<string, MushraVote>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
const str = (value: unknown): string => (typeof value === "string" ? value : "");

export function parseKit(html: string): KitConfig {
  const match = /<script id="kit" type="application\/json">([\s\S]*?)<\/script>/.exec(html);
  if (!match?.[1]) throw new Error("not a MixConsole listening kit (no embedded config)");
  const raw: unknown = JSON.parse(match[1]);
  if (!isRecord(raw) || typeof raw.kit_id !== "string") throw new Error("kit config is malformed");
  const ab = (Array.isArray(raw.ab) ? raw.ab : []).filter(isRecord).map((t) => ({
    id: str(t.id),
    pair: str(t.pair),
    title: str(t.title),
    left: str(t.left),
    right: str(t.right),
  }));
  const mushra = (Array.isArray(raw.mushra) ? raw.mushra : []).filter(isRecord).map((s) => ({
    pair: str(s.pair),
    title: str(s.title),
    reference: str(s.reference),
    items: (Array.isArray(s.items) ? s.items : []).map(str),
  }));
  const audio: Record<string, string> = {};
  if (isRecord(raw.audio))
    for (const [token, path] of Object.entries(raw.audio)) audio[token] = str(path);
  return { kit_id: raw.kit_id, ab, mushra, audio };
}

function hash(text: string): number {
  let h = 2166136261;
  for (const c of text) {
    h ^= c.charCodeAt(0);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function rng(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Deterministic per-rater shuffle (same algorithm as the standalone page). */
export function shuffled<T>(list: readonly T[], seed: number): T[] {
  const random = rng(seed);
  const out = [...list];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j] as T, out[i] as T];
  }
  return out;
}

export function orderFor<T>(kind: string, kit: KitConfig, rater: string, items: readonly T[]): T[] {
  return shuffled(items, hash(kind + kit.kit_id + rater));
}

export function emptyVotes(): VoteState {
  return { rater: "", ab: {}, mushra: {} };
}

export function recordAB(state: VoteState, trial: ABTrial, choice: ABVote["choice"]): VoteState {
  const vote: ABVote = {
    trial: trial.id,
    pair: trial.pair,
    left: trial.left,
    right: trial.right,
    choice,
  };
  return { ...state, ab: { ...state.ab, [trial.id]: vote } };
}

export function recordScore(
  state: VoteState,
  set: MushraSet,
  token: string,
  score: number,
): VoteState {
  const previous = state.mushra[set.pair]?.scores ?? {};
  const vote: MushraVote = { pair: set.pair, scores: { ...previous, [token]: Math.round(score) } };
  return { ...state, mushra: { ...state.mushra, [set.pair]: vote } };
}

export function buildVotes(kit: KitConfig, state: VoteState, now = new Date()) {
  return {
    version: "listen-votes/v1",
    kit_id: kit.kit_id,
    rater: state.rater || "anonymous",
    saved: now.toISOString(),
    ab: Object.values(state.ab),
    mushra: Object.values(state.mushra),
  };
}

export function votesFileName(kit: KitConfig, rater: string): string {
  return `votes-${(rater || "anonymous").replace(/[^A-Za-z0-9_-]+/g, "_")}-${kit.kit_id}.json`;
}

/** Resolve a kit audio path ("audio/<token>.m4a") against the files the user picked. */
export function findKitFile(files: readonly File[], relative: string): File | undefined {
  const wanted = relative.replace(/^\.?\//, "");
  return files.find((f) => {
    const path = f.webkitRelativePath || f.name;
    return path === wanted || path.endsWith(`/${wanted}`);
  });
}

export function progress(
  kit: KitConfig,
  state: VoteState,
): { ab: [number, number]; mushra: [number, number] } {
  return {
    ab: [Object.keys(state.ab).length, kit.ab.length],
    mushra: [Object.keys(state.mushra).length, kit.mushra.length],
  };
}
