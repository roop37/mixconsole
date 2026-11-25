import { useEffect, useMemo, useRef, useState } from "react";
import {
  type ABTrial,
  buildVotes,
  emptyVotes,
  findKitFile,
  type KitConfig,
  type MushraSet,
  orderFor,
  parseKit,
  progress,
  recordAB,
  recordScore,
  type VoteState,
  votesFileName,
} from "../lib/kit";

const storeKey = (kit: KitConfig) => `mixconsole-listen-${kit.kit_id}`;

function load(kit: KitConfig): VoteState {
  try {
    return { ...emptyVotes(), ...JSON.parse(localStorage.getItem(storeKey(kit)) ?? "{}") };
  } catch {
    return emptyVotes();
  }
}

function Player({ file, label }: { file: File | undefined; label: string }) {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file) return setUrl(null);
    const made = URL.createObjectURL(file);
    setUrl(made);
    return () => URL.revokeObjectURL(made);
  }, [file]);
  return (
    <div className="player">
      <strong>{label}</strong>
      <audio controls preload="none" src={url ?? undefined} aria-label={label} />
      {!file && <span className="muted"> (file missing from the chosen folder)</span>}
    </div>
  );
}

/**
 * Blind A/B voting on a kit built by `mixconsole listen build`. Pick the kit folder; the audio
 * is read from your disk in the browser (nothing is uploaded) and votes are saved as JSON.
 */
export function Listen() {
  const [kit, setKit] = useState<KitConfig | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [votes, setVotes] = useState<VoteState>(emptyVotes());
  const [tab, setTab] = useState<"ab" | "mushra">("ab");
  const [index, setIndex] = useState({ ab: 0, mushra: 0 });
  const [error, setError] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!kit) return;
    try {
      localStorage.setItem(storeKey(kit), JSON.stringify(votes));
    } catch {
      /* votes still save through the JSON download */
    }
  }, [kit, votes]);

  async function choose(list: FileList | null): Promise<void> {
    const picked = [...(list ?? [])];
    const page = picked.find((f) => (f.webkitRelativePath || f.name).endsWith("index.html"));
    if (!page) {
      setError("Choose the whole kit folder (it must contain index.html and audio/).");
      return;
    }
    try {
      const config = parseKit(await page.text());
      setKit(config);
      setFiles(picked);
      setVotes(load(config));
      setIndex({ ab: 0, mushra: 0 });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const trials = useMemo(
    () => (kit ? orderFor("ab", kit, votes.rater, kit.ab) : []),
    [kit, votes.rater],
  );
  const sets = useMemo(
    () => (kit ? orderFor("mushra", kit, votes.rater, kit.mushra) : []),
    [kit, votes.rater],
  );
  const audio = (token: string) => (kit ? findKitFile(files, kit.audio[token] ?? "") : undefined);

  function save(): void {
    if (!kit) return;
    const blob = new Blob([`${JSON.stringify(buildVotes(kit, votes), null, 2)}\n`], {
      type: "application/json",
    });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = votesFileName(kit, votes.rater);
    document.body.append(link);
    link.click();
    link.remove();
  }

  return (
    <div className="listen">
      <section className="panel" aria-label="Listening kit">
        <h2>Blind listening test</h2>
        <p className="muted">
          Build a kit with <code>mixconsole listen build -o DIR</code>, then choose that folder
          here. Items are tokenised, so you cannot tell which system made which transition. Votes
          stay in this browser until you save them as <code>listen-votes/v1</code> JSON for{" "}
          <code>mixconsole listen results</code>.
        </p>
        <div className="row">
          <button type="button" className="btn primary" onClick={() => picker.current?.click()}>
            Choose kit folder…
          </button>
          <input
            ref={picker}
            type="file"
            hidden
            multiple
            webkitdirectory=""
            aria-label="Choose listening kit folder"
            onChange={(e) => void choose(e.target.files)}
          />
          {kit && (
            <label>
              Your name or ID
              <input
                className="input"
                value={votes.rater}
                onChange={(e) => setVotes({ ...votes, rater: e.target.value.trim() })}
              />
            </label>
          )}
        </div>
        {error && (
          <p role="alert" className="notice error">
            {error}
          </p>
        )}
      </section>
      {kit && (
        <section className="panel" aria-label="Voting">
          <div role="tablist" className="lane-tabs">
            {(["ab", "mushra"] as const).map((t) => (
              <button
                type="button"
                key={t}
                role="tab"
                aria-selected={tab === t}
                className={`tab${tab === t ? " on" : ""}`}
                onClick={() => setTab(t)}
              >
                {t === "ab" ? "A/B comparison" : "Rating (0 to 100)"}
              </button>
            ))}
            <span className="muted" aria-live="polite">
              A/B {progress(kit, votes).ab.join("/")} · ratings started{" "}
              {progress(kit, votes).mushra.join("/")}
            </span>
          </div>
          {tab === "ab" ? (
            <ABView
              trial={trials[index.ab]}
              total={trials.length}
              at={index.ab}
              votes={votes}
              audio={audio}
              onVote={(trial, choice) => setVotes((v) => recordAB(v, trial, choice))}
              onMove={(n) => setIndex((i) => ({ ...i, ab: n }))}
            />
          ) : (
            <MushraView
              set={sets[index.mushra]}
              total={sets.length}
              at={index.mushra}
              votes={votes}
              kit={kit}
              audio={audio}
              onScore={(set, token, value) => setVotes((v) => recordScore(v, set, token, value))}
              onMove={(n) => setIndex((i) => ({ ...i, mushra: n }))}
            />
          )}
          <div className="row">
            <button type="button" className="btn primary" onClick={save}>
              Save votes as JSON
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => {
                if (confirm("Delete all votes stored in this browser for this kit?"))
                  setVotes({ ...emptyVotes(), rater: votes.rater });
              }}
            >
              Clear my votes
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

function ABView(props: {
  trial: ABTrial | undefined;
  total: number;
  at: number;
  votes: VoteState;
  audio(token: string): File | undefined;
  onVote(trial: ABTrial, choice: "left" | "right" | "tie"): void;
  onMove(n: number): void;
}) {
  const { trial, total, at, votes } = props;
  if (!trial) return <p className="empty">No A/B trials in this kit.</p>;
  const chosen = votes.ab[trial.id]?.choice;
  return (
    <div className="trial" data-testid="ab-trial">
      <p>
        Trial {at + 1} of {total}
      </p>
      <Player file={props.audio(trial.left)} label="A" />
      <Player file={props.audio(trial.right)} label="B" />
      <p>Which transition sounds better?</p>
      <div className="row" role="group" aria-label="Your choice">
        {(
          [
            ["left", "A is better"],
            ["tie", "No preference"],
            ["right", "B is better"],
          ] as const
        ).map(([value, text]) => (
          <button
            type="button"
            key={value}
            className={`btn${chosen === value ? " primary" : ""}`}
            aria-pressed={chosen === value}
            onClick={() => props.onVote(trial, value)}
          >
            {text}
          </button>
        ))}
      </div>
      <div className="row">
        <button
          type="button"
          className="btn"
          disabled={at === 0}
          onClick={() => props.onMove(at - 1)}
        >
          Previous
        </button>
        <button
          type="button"
          className="btn"
          disabled={at >= total - 1}
          onClick={() => props.onMove(at + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}

function MushraView(props: {
  set: MushraSet | undefined;
  total: number;
  at: number;
  votes: VoteState;
  kit: KitConfig;
  audio(token: string): File | undefined;
  onScore(set: MushraSet, token: string, value: number): void;
  onMove(n: number): void;
}) {
  const { set, total, at, votes, kit } = props;
  if (!set) return <p className="empty">No rating sets in this kit.</p>;
  const saved = votes.mushra[set.pair]?.scores ?? {};
  const items = orderFor(`items${set.pair}`, kit, votes.rater, set.items);
  return (
    <div className="trial">
      <p>
        Set {at + 1} of {total}
      </p>
      <Player file={props.audio(set.reference)} label="Original" />
      <p className="muted">
        Rate every item 0 to 100 (100 = as natural as the original). One of them is the original
        itself.
      </p>
      {items.map((token, n) => (
        <div key={token} className="rate">
          <Player file={props.audio(token)} label={`Item ${n + 1}`} />
          <label>
            Score
            <input
              type="range"
              min={0}
              max={100}
              value={saved[token] ?? 50}
              aria-valuetext={token in saved ? String(saved[token]) : "not rated"}
              onChange={(e) => props.onScore(set, token, Number(e.target.value))}
            />
            <output>{token in saved ? saved[token] : "-"}</output>
          </label>
        </div>
      ))}
      <div className="row">
        <button
          type="button"
          className="btn"
          disabled={at === 0}
          onClick={() => props.onMove(at - 1)}
        >
          Previous
        </button>
        <button
          type="button"
          className="btn"
          disabled={at >= total - 1}
          onClick={() => props.onMove(at + 1)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
