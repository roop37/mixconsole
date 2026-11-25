import type { Job, LibraryTrack, MixScript, TrackRecord } from "@mixconsole/schema-ts";
import type { Dispatch } from "react";
import { ApiError, api, followJob, initToken } from "./api/client";
import { redo as redoHistory, undo as undoHistory } from "./lib/history";
import { asMixScript, moveCue, planLocks, transitionOf } from "./lib/mixscript";
import { parseReport } from "./lib/report";
import { snapTime } from "./lib/snap";
import { type Action, type AppState, currentDoc, DECKS, type DeckId, renderFor } from "./state";

type Get = () => AppState;

function message(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) {
    return "The server refused the token. Open the URL printed by `mixconsole serve` (it ends in ?token=...).";
  }
  return error instanceof Error ? error.message : String(error);
}

function download(url: string, name: string): void {
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
}

/** All side effects live here; components only dispatch and call these. */
export function createActions(get: Get, dispatch: Dispatch<Action>) {
  const fail = (error: unknown) =>
    dispatch({ type: "notice", notice: { kind: "error", text: message(error) } });
  const info = (text: string) => dispatch({ type: "notice", notice: { kind: "info", text } });

  function projectId(): string {
    const id = get().project?.id;
    if (!id) throw new Error("no project yet");
    return id;
  }

  function busy(): boolean {
    const job = get().job;
    return job !== null && (job.state === "queued" || job.state === "running");
  }

  async function runJob(started: Job, label: string): Promise<Job> {
    dispatch({ type: "job-start", job: started, label });
    const done = await followJob(started.id, (event) => dispatch({ type: "job-progress", event }));
    dispatch({ type: "job-end", job: done });
    setTimeout(() => dispatch({ type: "job-clear", id: done.id }), 5000);
    if (done.state === "failed") throw new Error(done.error ?? "job failed");
    if (done.state === "cancelled") throw new Error("job cancelled");
    return done;
  }

  async function loadDeck(deck: DeckId, track: TrackRecord): Promise<void> {
    const project = projectId();
    const [lanes, peaks] = await Promise.all([
      api.lanes(project, track.hash),
      api.waveform(project, track.hash, 256),
    ]);
    dispatch({ type: "deck-data", deck, lanes, peaks });
  }

  async function ensureVersion(id: string): Promise<void> {
    if (get().versions[id]) return;
    dispatch({ type: "version-loaded", doc: await api.mixscript(projectId(), id) });
  }

  async function refreshRenders(): Promise<void> {
    dispatch({ type: "renders", renders: await api.renders(projectId()) });
  }

  async function refreshVersions(): Promise<void> {
    dispatch({ type: "versions", list: await api.mixscripts(projectId()) });
  }

  async function loadProject(id: string): Promise<void> {
    const project = (await api.projects()).find((p) => p.id === id);
    if (!project) return;
    dispatch({ type: "project", project });
    const tracks = await api.tracks(id);
    dispatch({ type: "clear-plan" });
    for (const [index, deck] of DECKS.entries()) {
      const track = tracks[index] ?? null;
      dispatch({ type: "track", deck, track });
      if (track?.analyzed) await loadDeck(deck, track);
    }
    const [versions, renders] = await Promise.all([api.mixscripts(id), api.renders(id)]);
    const a = tracks[0]?.hash;
    const b = tracks[1]?.hash;
    const latest = [...versions]
      .reverse()
      .find((v) => v.track_a === a && v.track_b === b && v.track_a && v.track_b);
    dispatch({ type: "versions", list: versions });
    dispatch({ type: "renders", renders });
    if (latest) {
      await ensureVersion(latest.id);
      dispatch({ type: "commit", id: latest.id });
    }
  }

  async function analyze(): Promise<void> {
    const { tracks } = get();
    const picked = DECKS.map((d) => tracks[d]).filter((t): t is TrackRecord => t !== null);
    if (picked.length === 0 || busy()) return;
    try {
      const fresh = await api.tracks(projectId());
      const byHash = new Map(fresh.map((t) => [t.hash, t]));
      let current = picked.map((t) => byHash.get(t.hash) ?? t);
      if (current.some((t) => !t.analyzed)) {
        const job = await api.analyze(
          projectId(),
          current.map((t) => t.hash),
        );
        await runJob(job, "Analysis");
        const after = new Map((await api.tracks(projectId())).map((t) => [t.hash, t]));
        current = current.map((t) => after.get(t.hash) ?? t);
      }
      for (const deck of DECKS) {
        const track = current.find((t) => t.hash === get().tracks[deck]?.hash);
        if (track) {
          dispatch({ type: "track", deck, track });
          await loadDeck(deck, track);
        }
      }
    } catch (error) {
      fail(error);
    }
  }

  async function assign(deck: DeckId, track: TrackRecord): Promise<void> {
    dispatch({ type: "clear-plan" });
    dispatch({ type: "track", deck, track });
    const { tracks } = get();
    if (tracks.a && tracks.b) await analyze();
    else if (track.analyzed) await loadDeck(deck, track).catch(fail);
  }

  async function sharedHash(): Promise<{ a: string; b: string }> {
    const { tracks } = get();
    if (!tracks.a || !tracks.b) throw new Error("load a track on both decks first");
    return { a: tracks.a.hash, b: tracks.b.hash };
  }

  async function adoptVersion(id: string): Promise<void> {
    await ensureVersion(id);
    dispatch({ type: "commit", id });
    await Promise.all([refreshVersions(), refreshRenders()]);
  }

  let initialised = false;
  // Edits save in the background; anything that renders or exports waits for them first.
  let saving: Promise<void> = Promise.resolve();
  let lastDraft: MixScript | null = null;

  return {
    async init(): Promise<void> {
      if (initialised) return;
      initialised = true;
      try {
        initToken();
        const projects = await api.projects();
        dispatch({ type: "ready", projects });
        const latest = [...projects].sort((x, y) => y.created_at - x.created_at)[0];
        if (latest) await loadProject(latest.id);
        else {
          const created = await api.createProject("Session");
          dispatch({ type: "project", project: created, projects: [created] });
        }
      } catch (error) {
        dispatch({ type: "ready", projects: [] });
        fail(error);
      }
    },

    async newSession(): Promise<void> {
      try {
        const created = await api.createProject(`Session ${new Date().toLocaleString()}`);
        dispatch({ type: "reset-session" });
        dispatch({ type: "project", project: created, projects: [created, ...get().projects] });
      } catch (error) {
        fail(error);
      }
    },

    loadProject: (id: string) => loadProject(id).catch(fail),

    async uploadFile(deck: DeckId, file: File): Promise<void> {
      dispatch({ type: "uploading", deck, name: file.name });
      try {
        await assign(deck, await api.upload(projectId(), file));
      } catch (error) {
        dispatch({ type: "uploading", deck, name: null });
        fail(error);
      }
    },

    async addPath(deck: DeckId, path: string): Promise<void> {
      try {
        const [track] = await api.addTracks(projectId(), [path.trim()]);
        if (track) await assign(deck, track);
      } catch (error) {
        fail(error);
      }
    },

    async loadLibraryTrack(deck: DeckId, track: LibraryTrack): Promise<void> {
      dispatch({ type: "view", view: "console" });
      await this.addPath(deck, track.path);
    },

    clearDeck(deck: DeckId): void {
      dispatch({ type: "clear-plan" });
      dispatch({ type: "track", deck, track: null });
    },

    analyze,

    async plan(): Promise<void> {
      if (busy()) return;
      try {
        const { a, b } = await sharedHash();
        const { options } = get();
        const job = await api.mix(projectId(), {
          a,
          b,
          style: options.style,
          candidates: options.candidates,
          stems: options.stems,
        });
        const done = await runJob(job, "Plan, verify and render");
        const result = done.result ?? {};
        const mixscriptId = String(result.mixscript_id);
        const renderId = String(result.render_id);
        await ensureVersion(mixscriptId);
        dispatch({ type: "commit", id: mixscriptId });
        await Promise.all([refreshVersions(), refreshRenders()]);
        const report = parseReport(await api.renderFileJson(projectId(), renderId, "report.json"));
        dispatch({ type: "plan-render", renderId, report });
        dispatch({ type: "select", patch: { candidateId: report.chosenId } });
      } catch (error) {
        fail(error);
      }
    },

    /** Re-plan from the current version, keeping its locks (and any extra lock values). */
    async replan(extra: Record<string, unknown> = {}, extraLocks: string[] = []): Promise<void> {
      const doc = currentDoc(get());
      if (!doc || busy()) return;
      try {
        const { a, b } = await sharedHash();
        const { options, history } = get();
        const transition = transitionOf(doc);
        const locks = { ...(planLocks(doc) ?? {}), ...extra };
        const job = await api.plan(projectId(), {
          a,
          b,
          style: options.style,
          candidates: options.candidates,
          stems: options.stems,
          parent_id: history.current,
          locks: Object.keys(locks).length > 0 ? locks : null,
        });
        const done = await runJob(job, "Re-plan");
        const planned = String(done.result?.mixscript_id);
        await ensureVersion(planned);
        // The planner does not write MixScript locks; re-apply them so they survive the re-plan.
        const stored = get().versions[planned];
        if (!stored) return;
        const next = asMixScript(structuredClone(stored.document));
        const kept = new Set([...(transition.locks ?? []), ...extraLocks]);
        const nextTransition = transitionOf(next);
        const laneIds = new Set((nextTransition.automation ?? []).map((l) => l.id));
        const allowed = new Set([
          "exit",
          "entry",
          "length_bars",
          "family",
          "tempo",
          "key",
          ...laneIds,
        ]);
        nextTransition.locks = [...kept].filter((name) => allowed.has(name)).sort();
        await this.commitEdit(next, "re-plan (locks kept)", planned);
        dispatch({ type: "plan-render", renderId: null, report: null });
      } catch (error) {
        fail(error);
      }
    },

    commitEdit(doc: MixScript, label: string, parent?: string): Promise<void> {
      const save = async (): Promise<void> => {
        try {
          const { a, b } = await sharedHash();
          const saved = await api.addMixscript(projectId(), {
            document: doc as unknown as Record<string, unknown>,
            parent_id: parent ?? get().history.current,
            track_a: a,
            track_b: b,
            label,
          });
          await adoptVersion(saved.id);
        } catch (error) {
          dispatch({ type: "draft", doc: null });
          fail(error);
        }
      };
      saving = saving.then(save);
      return saving;
    },

    setDraft: (doc: MixScript | null) => dispatch({ type: "draft", doc }),

    /** Save the live (dragged or nudged) edit as a new MixScript version. */
    async commitDraft(label = "edit"): Promise<void> {
      const draft = get().draft;
      if (!draft || draft === lastDraft) return saving;
      lastDraft = draft;
      return this.commitEdit(draft, label);
    },

    /** Snap-and-commit a cue edit (used by keyboard nudges; drags use setDraft then commitEdit). */
    async moveCue(deck: DeckId, seconds: number): Promise<void> {
      const doc = currentDoc(get());
      const lanes = get().lanes[deck];
      if (!doc || !lanes) return;
      const which = deck === "a" ? "exit" : "entry";
      const snapped = snapTime(seconds, lanes, get().options.snap);
      await this.commitEdit(moveCue(doc, which, snapped, lanes, "off"), `move ${which} cue`);
    },

    async undo(): Promise<void> {
      const target = undoHistory(get().history).current;
      if (!target || target === get().history.current) return;
      try {
        await ensureVersion(target);
        dispatch({ type: "undo" });
      } catch (error) {
        fail(error);
      }
    },

    async redo(): Promise<void> {
      const target = redoHistory(get().history).current;
      if (!target || target === get().history.current) return;
      try {
        await ensureVersion(target);
        dispatch({ type: "redo" });
      } catch (error) {
        fail(error);
      }
    },

    async render(format: "wav" | "flac" = "wav"): Promise<string | null> {
      await this.commitDraft("edit");
      await saving;
      const id = get().history.current;
      if (!id || busy()) return null;
      try {
        const job = await api.render(projectId(), id, format);
        const done = await runJob(job, `Render ${format.toUpperCase()}`);
        await refreshRenders();
        return String(done.result?.render_id ?? "");
      } catch (error) {
        fail(error);
        return null;
      }
    },

    async exportAudio(format: "wav" | "flac"): Promise<void> {
      await this.commitDraft("edit");
      await saving;
      const id = get().history.current;
      if (!id) return;
      let record = renderFor(get(), format);
      if (!record) {
        const rendered = await this.render(format);
        if (!rendered) return;
        record = renderFor(get(), format);
      }
      if (!record) return;
      download(
        api.renderFileUrl(projectId(), record.id, record.audio),
        `mix-${record.id}.${format}`,
      );
      info(`Exported ${record.audio} (render ${record.id}).`);
    },

    exportMixScript(): void {
      const doc = currentDoc(get());
      const id = get().history.current;
      if (!doc || !id) return;
      const blob = new Blob([`${JSON.stringify(doc, null, 2)}\n`], { type: "application/json" });
      download(URL.createObjectURL(blob), `mixscript-${id}.json`);
      info("Exported the MixScript.");
    },

    reportUrl(): string | null {
      const record = renderFor(get()) ?? get().renders.find((r) => r.id === get().planRenderId);
      return record?.files.includes("report.html")
        ? api.renderFileUrl(projectId(), record.id, "report.html")
        : null;
    },

    async cancelJob(): Promise<void> {
      const job = get().job;
      if (job) await api.cancel(job.id).catch(fail);
    },

    dismissNotice: () => dispatch({ type: "notice", notice: null }),
    info,
    fail,
  };
}

export type Actions = ReturnType<typeof createActions>;
