import type { Lanes } from "@mixconsole/schema-ts";
import { useEffect, useRef } from "react";
import { normaliseEnergy, pickVisible, sectionHue, timeToX, type View } from "../lib/lanes";

export const LANE_ROWS = [
  { id: "beats", label: "Beats", height: 14 },
  { id: "bars", label: "Bars", height: 16 },
  { id: "phrases", label: "Phrases", height: 18 },
  { id: "sections", label: "Sections", height: 18 },
  { id: "vocals", label: "Vocals", height: 14 },
  { id: "energy", label: "Energy", height: 30 },
] as const;

export const LANES_HEIGHT = LANE_ROWS.reduce((sum, row) => sum + row.height, 0);

const C = {
  line: "#2b3648",
  tick: "#6f8199",
  bar: "#98a8bd",
  text: "#c6d0de",
  label: "rgba(13,16,21,0.78)",
  vocal: "#d46ba3",
  energyLow: "#2d6a8f",
  energyHigh: "#f0b429",
};

function draw(
  canvas: HTMLCanvasElement,
  lanes: Lanes,
  view: View,
  width: number,
  accent: string,
): void {
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(LANES_HEIGHT * ratio);
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, LANES_HEIGHT);
  ctx.font = "10px system-ui, sans-serif";
  ctx.textBaseline = "middle";
  const pps = width / (view.end - view.start);
  const x = (t: number) => timeToX(t, view, width);
  // Lane names are drawn as chips at the left edge; data labels start to their right.
  const chip = Math.max(...LANE_ROWS.map((row) => ctx.measureText(row.label).width)) + 12;

  let top = 0;
  for (const row of LANE_ROWS) {
    const mid = top + row.height / 2;
    ctx.fillStyle = "rgba(255,255,255,0.025)";
    ctx.fillRect(0, top, width, row.height - 1);

    if (row.id === "beats" && pps >= 5) {
      const [from, to] = pickVisible(lanes.beats, view, 1);
      ctx.strokeStyle = C.tick;
      ctx.beginPath();
      for (let i = from; i < to; i++) {
        const px = Math.round(x(lanes.beats[i] as number)) + 0.5;
        ctx.moveTo(px, top + 3);
        ctx.lineTo(px, top + row.height - 4);
      }
      ctx.stroke();
    }

    if (row.id === "bars") {
      const starts = lanes.bars.map((b) => b.start);
      const [from, to] = pickVisible(
        starts,
        view,
        lanes.bars.length ? (lanes.bars[0]?.end ?? 0) : 0,
      );
      const barWidth = lanes.bars[0] ? (lanes.bars[0].end - lanes.bars[0].start) * pps : 0;
      const labelEvery = barWidth >= 26 ? 1 : barWidth >= 12 ? 4 : barWidth >= 5 ? 16 : 0;
      for (let i = from; i < to; i++) {
        const bar = lanes.bars[i];
        if (!bar) continue;
        const left = x(bar.start);
        ctx.fillStyle = i % 2 === 0 ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.02)";
        ctx.fillRect(left, top, Math.max(1, (bar.end - bar.start) * pps - 1), row.height - 1);
        if (labelEvery && i % labelEvery === 0 && left + 3 >= chip) {
          ctx.fillStyle = C.bar;
          ctx.fillText(String(i + 1), left + 3, mid);
        }
      }
    }

    if (row.id === "phrases") {
      for (const [i, phrase] of lanes.phrases.entries()) {
        const next = lanes.phrases[i + 1]?.start ?? lanes.duration;
        if (next < view.start || phrase.start > view.end) continue;
        const left = x(phrase.start);
        const right = x(next);
        ctx.fillStyle = `hsla(${accent === "a" ? 175 : 35}, 45%, 45%, ${0.12 + 0.2 * phrase.confidence})`;
        ctx.fillRect(left, top + 1, Math.max(1, right - left - 1), row.height - 3);
        ctx.fillStyle = C.text;
        const textX = Math.max(left + 4, chip);
        if (right - textX > 60) ctx.fillText(`P${i + 1} · ${phrase.length_bars} bars`, textX, mid);
      }
    }

    if (row.id === "sections") {
      for (const section of lanes.sections) {
        if (section.end < view.start || section.start > view.end) continue;
        const left = x(section.start);
        const right = x(section.end);
        ctx.fillStyle = `hsla(${sectionHue(section.label)}, 50%, 42%, 0.55)`;
        ctx.fillRect(left, top + 1, Math.max(1, right - left - 1), row.height - 3);
        ctx.fillStyle = "#fff";
        const textX = Math.max(left + 4, chip);
        if (right - textX > 48) ctx.fillText(section.label ?? "section", textX, mid);
      }
    }

    if (row.id === "vocals") {
      ctx.fillStyle = C.vocal;
      for (const span of lanes.vocals) {
        if (span.end < view.start || span.start > view.end) continue;
        ctx.fillRect(
          x(span.start),
          top + 3,
          Math.max(1, (span.end - span.start) * pps),
          row.height - 7,
        );
      }
    }

    if (row.id === "energy") {
      const energy = normaliseEnergy(lanes.bar_energy);
      for (const [i, value] of energy.entries()) {
        const bar = lanes.bars[i];
        if (!bar || bar.end < view.start || bar.start > view.end) continue;
        const h = Math.max(1, value * (row.height - 4));
        ctx.fillStyle = value > 0.66 ? C.energyHigh : value > 0.33 ? "#7aa7c9" : C.energyLow;
        ctx.fillRect(
          x(bar.start),
          top + row.height - 2 - h,
          Math.max(1, (bar.end - bar.start) * pps - 1),
          h,
        );
      }
    }

    // row label chip, drawn over the data so the lane names stay visible at any zoom
    ctx.fillStyle = C.label;
    const labelWidth = ctx.measureText(row.label).width + 8;
    ctx.fillRect(0, top, labelWidth, row.height - 1);
    ctx.fillStyle = C.text;
    ctx.fillText(row.label, 4, mid);
    top += row.height;
  }
  ctx.strokeStyle = C.line;
  ctx.strokeRect(0.5, 0.5, width - 1, LANES_HEIGHT - 1);
}

interface Props {
  lanes: Lanes;
  view: View;
  width: number;
  deck: "a" | "b";
}

export function LaneCanvas({ lanes, view, width, deck }: Props) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (ref.current && width > 0 && view.end > view.start)
      draw(ref.current, lanes, view, width, deck);
  }, [lanes, view, width, deck]);
  return (
    <canvas
      ref={ref}
      className="lane-canvas"
      style={{ width, height: LANES_HEIGHT }}
      role="img"
      aria-label={`Analysis lanes for deck ${deck.toUpperCase()}: beats, bars, phrases, sections, vocals and energy`}
    />
  );
}
