import type { LibraryTrack } from "@mixconsole/schema-ts";
import { useEffect, useId, useRef, useState } from "react";
import { api } from "../api/client";
import { basename, fmtNum } from "../lib/format";
import type { DeckId } from "../state";
import { useStore } from "../store";

const ACCEPT = "audio/*,.wav,.flac,.mp3,.m4a,.ogg,.opus,.aif,.aiff";

/** Empty-deck drop zone: drop or pick a file (uploaded to the local server), a server path, or a library track. */
export function Intake({ deck }: { deck: DeckId }) {
  const { state, actions } = useStore();
  const letter = deck.toUpperCase();
  const [over, setOver] = useState(false);
  const [path, setPath] = useState("");
  const [library, setLibrary] = useState<LibraryTrack[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const pathId = useId();
  const libraryId = useId();
  const uploading = state.uploading[deck];

  useEffect(() => {
    api
      .library({ limit: 200 })
      .then(setLibrary)
      .catch(() => setLibrary([]));
  }, []);

  function take(files: FileList | File[]): void {
    const list = [...files];
    const other: DeckId = deck === "a" ? "b" : "a";
    const first = list[0];
    if (first) void actions.uploadFile(deck, first);
    const second = list[1];
    if (second && !state.tracks[other]) void actions.uploadFile(other, second);
  }

  return (
    <div
      className={`intake deck-${deck}${over ? " over" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        take(event.dataTransfer.files);
      }}
    >
      <div className="intake-main">
        <span className="deck-chip">{letter}</span>
        {uploading ? (
          <p role="status">Uploading {uploading}…</p>
        ) : (
          <>
            <p className="intake-title">Drop an audio file for deck {letter}</p>
            <button type="button" className="btn" onClick={() => input.current?.click()}>
              Choose file…
            </button>
            <input
              ref={input}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              aria-label={`Choose audio file for deck ${letter}`}
              onChange={(event) => {
                if (event.target.files) take(event.target.files);
                event.target.value = "";
              }}
            />
          </>
        )}
      </div>
      <div className="intake-alt">
        <label htmlFor={pathId}>File path on this computer</label>
        <form
          className="row"
          onSubmit={(event) => {
            event.preventDefault();
            if (path.trim()) void actions.addPath(deck, path);
          }}
        >
          <input
            id={pathId}
            className="input"
            value={path}
            placeholder="/Users/me/Music/track.flac"
            onChange={(event) => setPath(event.target.value)}
          />
          <button type="submit" className="btn" disabled={!path.trim()}>
            Add
          </button>
        </form>
        <label htmlFor={libraryId}>Or from the library</label>
        <select
          id={libraryId}
          className="input"
          value=""
          onChange={(event) => {
            const picked = library.find((t) => t.hash === event.target.value);
            if (picked) void actions.loadLibraryTrack(deck, picked);
          }}
        >
          <option value="">{library.length ? "Pick a track…" : "Library is empty"}</option>
          {library.map((t) => (
            <option key={t.hash} value={t.hash}>
              {basename(t.path)} · {fmtNum(t.bpm, 0)} BPM · {t.camelot || "n/a"}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
