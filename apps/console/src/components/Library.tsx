import type { LibraryStats, LibraryTrack } from "@mixconsole/schema-ts";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { basename, fmtNum, fmtTime } from "../lib/format";
import { type SortDir, type SortKey, sortTracks } from "../lib/libsort";
import { useStore } from "../store";

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "name", label: "Track" },
  { key: "bpm", label: "BPM", numeric: true },
  { key: "key", label: "Key", numeric: true },
  { key: "energy", label: "Energy", numeric: true },
  { key: "lufs", label: "LUFS", numeric: true },
  { key: "duration", label: "Length", numeric: true },
];

export function Library() {
  const { actions } = useStore();
  const [q, setQ] = useState("");
  const [bpmMin, setBpmMin] = useState("");
  const [bpmMax, setBpmMax] = useState("");
  const [camelot, setCamelot] = useState("");
  const [tracks, setTracks] = useState<LibraryTrack[]>([]);
  const [stats, setStats] = useState<LibraryStats | null>(null);
  const [sort, setSort] = useState<{ key: SortKey; dir: SortDir }>({ key: "bpm", dir: "asc" });
  const [folder, setFolder] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    api
      .library({
        q: q || undefined,
        bpm_min: bpmMin ? Number(bpmMin) : undefined,
        bpm_max: bpmMax ? Number(bpmMax) : undefined,
        camelot: camelot || undefined,
        limit: 500,
      })
      .then((rows) => {
        setTracks(rows);
        setError(null);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
    api
      .libraryStats()
      .then(setStats)
      .catch(() => setStats(null));
  }, [q, bpmMin, bpmMax, camelot]);

  useEffect(() => {
    const handle = setTimeout(refresh, 250);
    return () => clearTimeout(handle);
  }, [refresh]);

  const rows = useMemo(() => sortTracks(tracks, sort.key, sort.dir), [tracks, sort]);

  async function scan(): Promise<void> {
    try {
      const job = await api.scan(folder.trim());
      actions.info(
        `Library scan started (job ${job.id.slice(0, 8)}). Results appear as files are analysed.`,
      );
      setTimeout(refresh, 4000);
    } catch (e) {
      actions.fail(e);
    }
  }

  return (
    <div className="library">
      <section className="panel" aria-label="Library filters">
        <h2>Library</h2>
        <form className="filters" onSubmit={(e) => e.preventDefault()}>
          <label>
            Search
            <input
              className="input"
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="name or path"
            />
          </label>
          <label>
            BPM from
            <input
              className="input narrow"
              inputMode="numeric"
              value={bpmMin}
              onChange={(e) => setBpmMin(e.target.value)}
            />
          </label>
          <label>
            to
            <input
              className="input narrow"
              inputMode="numeric"
              value={bpmMax}
              onChange={(e) => setBpmMax(e.target.value)}
            />
          </label>
          <label>
            Camelot key
            <input
              className="input narrow"
              value={camelot}
              onChange={(e) => setCamelot(e.target.value.toUpperCase())}
              placeholder="8A"
            />
          </label>
          <span className="muted" aria-live="polite">
            {stats
              ? `${stats.tracks} tracks, ${stats.failures} failures, ${fmtTime(stats.total_duration)} total`
              : ""}
          </span>
        </form>
        <form
          className="row scan"
          onSubmit={(e) => {
            e.preventDefault();
            if (folder.trim()) void scan();
          }}
        >
          <label htmlFor="scan-folder">Scan a folder on this computer</label>
          <input
            id="scan-folder"
            className="input wide"
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            placeholder="/Users/me/Music"
          />
          <button type="submit" className="btn" disabled={!folder.trim()}>
            Scan
          </button>
        </form>
      </section>
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      <div className="table-wrap">
        <table className="tracks">
          <thead>
            <tr>
              {COLUMNS.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  aria-sort={
                    sort.key === c.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none"
                  }
                  className={c.numeric ? "num" : ""}
                >
                  <button
                    type="button"
                    className="th-btn"
                    onClick={() =>
                      setSort((s) => ({
                        key: c.key,
                        dir: s.key === c.key && s.dir === "asc" ? "desc" : "asc",
                      }))
                    }
                  >
                    {c.label}
                    {sort.key === c.key ? (sort.dir === "asc" ? " ▲" : " ▼") : ""}
                  </button>
                </th>
              ))}
              <th scope="col">Load</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={COLUMNS.length + 1} className="empty">
                  No tracks yet. Scan a folder, or analyse tracks on the decks: they are indexed
                  here.
                </td>
              </tr>
            )}
            {rows.map((t) => (
              <tr key={t.hash}>
                <td title={t.path}>{basename(t.path)}</td>
                <td className="num">{fmtNum(t.bpm, 1)}</td>
                <td className="num">{t.camelot || "n/a"}</td>
                <td className="num">{fmtNum(t.energy_mean, 2)}</td>
                <td className="num">{fmtNum(t.lufs, 1)}</td>
                <td className="num">{fmtTime(t.duration)}</td>
                <td className="actions">
                  <button
                    type="button"
                    className="btn"
                    aria-label={`Load ${basename(t.path)} on deck A`}
                    onClick={() => void actions.loadLibraryTrack("a", t)}
                  >
                    A
                  </button>
                  <button
                    type="button"
                    className="btn"
                    aria-label={`Load ${basename(t.path)} on deck B`}
                    onClick={() => void actions.loadLibraryTrack("b", t)}
                  >
                    B
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
