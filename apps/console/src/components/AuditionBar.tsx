import { LEAD_IN, type Slot, useAudition } from "../audition";
import { fmtNum } from "../lib/format";

/** Two-slot A/B audition: switching keeps the position relative to the handoff. */
export function AuditionBar() {
  const audition = useAudition();
  const { sources, slots, active, playing, rel } = audition;
  return (
    <section className="audition" aria-label="A/B audition">
      <div className="audition-slots">
        {(["a", "b"] as Slot[]).map((slot) => (
          <div key={slot} className={`slot${active === slot ? " on" : ""}`}>
            <button
              type="button"
              className="btn slot-btn"
              aria-pressed={active === slot}
              aria-keyshortcuts={slot}
              disabled={!slots[slot]}
              onClick={() => audition.switchTo(slot)}
            >
              {slot.toUpperCase()}
            </button>
            <select
              className="input"
              aria-label={`Audition source ${slot.toUpperCase()}`}
              value={slots[slot] ?? ""}
              onChange={(event) => audition.setSlot(slot, event.target.value || null)}
            >
              <option value="">{sources.length ? "none" : "no previews yet"}</option>
              {sources.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        ))}
      </div>
      <div className="audition-transport">
        <button
          type="button"
          className="btn primary"
          disabled={!slots[active]}
          aria-keyshortcuts="Enter"
          onClick={() => audition.toggle()}
        >
          {playing ? "Pause" : "Play"}
        </button>
        <input
          type="range"
          aria-label="Audition position relative to the handoff"
          min={-LEAD_IN * 2}
          max={14}
          step={0.1}
          value={Math.max(-LEAD_IN * 2, Math.min(14, rel))}
          disabled={!slots[active]}
          onChange={(event) => audition.seekRel(Number(event.target.value))}
        />
        <output className="timecode" aria-label="Seconds from the handoff">
          {rel >= 0 ? "+" : ""}
          {fmtNum(rel, 1)} s
        </output>
      </div>
    </section>
  );
}
