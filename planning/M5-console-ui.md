# M5: Console UI (2026-11-26)

Built on M4.5 at commit 7d461e4 (changes uncommitted for lead review).

## Checklist

- [x] 1. `apps/console`: React 19.2.9, Vite 7.3.8, TypeScript 5.9.3 strict (`noUncheckedIndexedAccess`),
  wavesurfer.js 7.12.12, Biome 2.6.9, Vitest 3.2.7, Playwright 1.65.1; pnpm 10.33.0 workspace (root
  `pnpm-workspace.yaml`, `packageManager` pin). Exact versions, listed in `apps/console/THIRD_PARTY.md`.
- [x] 2. Load tracks: drop/choose a file (uploaded to the local server), type a server path, or pick from the
  library; analysis starts when both decks are filled, with an SSE-driven progress bar and cancel. Decks A/B:
  wavesurfer waveform (server peaks) + lanes for beats, bars, phrases, sections, vocals, energy; zoom, fit,
  transport, cue markers and the transition region.
- [x] 3. Plan: style, candidate count and stems `off`/`auto`/`on` (default off) -> plan + verify + render job.
  Candidate cards: family, length (bars and seconds), exit/entry, total score, per-feature breakdown, verify
  status (Verified / Failed + reason / Not verified), seam measurements with `n/a` for unmeasured values,
  rejected-by-constraint summary. A/B audition (two slots, position kept relative to the handoff) of the candidate
  previews and of the seam of the current render.
- [x] 4. Edit: drag EXIT/ENTRY flags (snap phrase | downbeat | beat | off; Alt bypasses), keyboard nudges
  (beat, bar, phrase), family and length changes and "Use this" candidate (re-plan with locks), lock toggles for
  family/exit/entry/length/lane, re-plan keeping locks, gain/EQ/filter automation editor (drag, add, delete, curve
  type), undo/redo over append-only MixScript versions, re-render.
- [x] 5. Export WAV, FLAC, MixScript JSON and the HTML report; library view with search, BPM range, Camelot key and
  sort by BPM/key/energy/LUFS/length, and folder scan.
- [x] 6. Blind A/B + rating page that reads a kit built by `mixconsole listen build` (folder picked in the browser,
  nothing uploaded) and saves `listen-votes/v1` JSON accepted by `mixconsole listen results`.
- [x] 7. Design: dark dense DJ-tool layout, system fonts only, keyboard shortcuts (`?`), labelled controls,
  `role=slider` cue and point handles with `aria-valuetext`, visible focus, skip link, tablists; checked at 1280 px
  (no horizontal overflow, asserted in Playwright) and 1920 px.
- [x] 8. Tests: 43 Vitest unit tests (snap, MixScript edits, history, automation maths, lane maths, report parsing and
  `n/a`, library sort, kit/votes, reducer); Playwright smoke on synthetic audio (below); Python tests for the
  static mount, uploads, stems param, FLAC render and the generated types.
- [x] 9. `mixconsole serve --ui [--ui-dir DIR]` serves the built app (same origin, `?token=` moved to
  `sessionStorage`); explicit missing dir exits 1. `scripts/check-ui.sh` and a CI `ui` job; `scripts/check.sh` untouched
  apart from the type drift check now covering the MixScript types.

## Server additions (needed by the UI, all additive)

- `POST /projects/{id}/uploads?name=` raw body (browser drops have no path); deduplicated by content hash,
  `artifacts/uploads/<hash16>/<name>`, 2 GiB cap, audio extensions only, partial files cleaned up.
- `stems` on `plans`/`mixes` requests via `config.settings_override` (a ContextVar, thread-local to the job).
- `format` (`wav`|`flac`) on `renders`.
- `scripts/gen_api_types.py` also emits `packages/schema-ts/src/mixscript.d.ts` (from `schemas/mixscript-v1.1.json`)
  and `index.d.ts`; `--check` covers all four files. MixScript documents are opaque in the API, so the console casts
  the document once, in `lib/mixscript.ts#asMixScript`.

## Screenshots (synthetic audio only, produced by the Playwright run)

| File | Content |
| --- | --- |
| `docs/screenshots/01-empty-1920.png` | Empty decks, drop zones |
| `docs/screenshots/02-decks-analysed-1920.png` | Both decks analysed |
| `docs/screenshots/03-plan-candidates-1920.png` | Planned: cues, candidates, audition, edit panel |
| `docs/screenshots/04-edited-rendered-1920.png` | After a cue move, re-rendered |
| `docs/screenshots/05-library-1920.png` | Library sorted by BPM |
| `docs/screenshots/06-console-1280.png` | Console at 1280 px |
| `docs/screenshots/07-listen-1920.png` | Blind voting page with a synthetic kit |

## Playwright smoke (`apps/console/e2e/smoke.spec.ts`)

Global setup generates two synthetic songs (`mixconsole.testing.synth`), builds a synthetic listening kit and starts
`mixconsole serve --ui` on a throwaway data dir. Steps: open with token (token leaves the URL) -> drop two files ->
analysis progress -> lanes on both decks -> Plan mix -> candidate cards (bars, score, verify status) -> audition a
preview (playing, position advances) -> drag the exit cue (changes, "on phrase", locked) -> undo/redo -> keyboard
nudge -> drag an automation point -> Re-render -> export WAV (RIFF) and MixScript (v1.1, `exit` lock) -> library
list/sort -> 1280 px no overflow -> no request leaves 127.0.0.1, no console errors. Second test: blind voting page
reads the kit, records a vote, saves `listen-votes/v1`. Third: no token shows an explanatory alert.

## Limits

- Moving a cue drops the transition's `render.beat_warp` (it belongs to the old cue); the renderer then uses the
  constant tempo map. A re-plan with locked cues succeeds only if the planner has a candidate at exactly those cues.
- Candidate previews exist only for the plan made by "Plan mix" (the `mix` job); re-plans and edits are auditioned
  through the rendered seam of the current version (needs "Re-render").
- Stems choice affects planning/verification; analysis processes use the server `stems` setting.
- `mixconsole serve --ui` finds `apps/console/dist` in a checkout (or `--ui-dir`, `MIXCONSOLE_UI_DIR`,
  `mixconsole/_ui`); the wheel does not bundle the build yet.
- Waveform peaks are the 256 samples/pixel level; very long tracks at high zoom use that resolution only.
- Playback of the deck waveform uses the server's Opus preview (WAV without ffmpeg), not the source file.
- No automated screen-reader or contrast run; contrast was chosen from tokens (text 15:1, muted 7:1 on panels) and
  checked by eye only. Not yet tried on Safari or Firefox (Playwright ran Chromium only).
- Not yet validated on real songs in the UI (synthetic only, by rule). Waveforms of the synthetic songs are flat.
- Upload of a very large file reads it through one request body; no resumable upload.

## Final checks

`scripts/check.sh` (Python gate, 53 s wall, coverage 93.60 %, floor 91):

```text
All checks passed!
158 files already formatted
0 errors, 0 warnings, 0 informations
API types up to date
312 passed in 46.20s
scripts/check.sh  173.07s user 17.45s system 356% cpu 53.466 total
```

`scripts/check-ui.sh` (pnpm install --frozen-lockfile, type drift, Biome, tsc, Vitest, Vite build, Playwright):

```text
Checked 46 files ... No fixes applied.            (Biome: 0 errors, 0 warnings)
tsc --noEmit                                      (strict, clean)
Test Files  9 passed (9)   Tests  43 passed (43)
vite build: dist/assets/index-*.js 308 kB (gzip 98 kB), index-*.css 13 kB (gzip 3.5 kB)
  3 passed (38.1s)   (smoke 30.1 s, voting 0.3 s, token 0.1 s)
exit=0
```
