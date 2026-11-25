# M4: Bench + listening (2026-11-26)

Built on M3 at commit 07ca659 (changes uncommitted for lead review).

## Checklist

- [x] 1. Corpus `bench/pairs.yaml`: 37 tracks, 36 pairs (28 same-genre, 8 cross-genre). Licence, attribution and
  source URL per track. `bench corpus --fetch` re-reads each track page, requires the licence on the page to equal
  the manifest (CC0-1.0 / CC-BY-3.0 / CC-BY-4.0, no NC/ND/SA) and only then downloads into
  `~/.cache/mixconsole/corpus/audio/`. All 37 fetched cleanly. Audio is never committed.
- [x] 2. Systems: `linear6` (plain 6 s linear crossfade of the two track ends), `trim_eqpower` (silence trimmed at -50 dBFS,
  6 s equal-power crossfade), MixConsole `smooth`, `auto`, `club` (full `mix_pair`: plan, verify, fallback).
  Optional `automix_engine` (VertexSelection/automix-engine, LGPL-2.1): `scripts/setup_automix_engine.sh` clones it
  into `~/.cache/mixconsole/external/automix-engine/` with its own Python 3.12 venv (installed in about 3 minutes);
  it runs only as a subprocess on a scratch copy, nothing imported or vendored (noted in THIRD_PARTY.md).
  Its inputs are re-encoded to 44.1 kHz stereo MP3 first, because it rejects the raw MP3s' frame count. About 2.5 to
  3 min per pair on this M4 (Demucs inside), so it was run on 2 pairs only.
- [x] 3. `mixconsole bench corpus [--limit N | --quick | --budget-minutes M | --systems ... | --fetch]` writes
  `bench-result/v1` (kind `corpus`), per pair x system rows (`bench/results/rows/`), a per-system table in
  `bench/results/LATEST.md` and a `listen-input.json` with 40 s excerpts. Pairs run in a fixed interleaved order so a
  limit still spans genres. Unmeasured metrics are absent from the result and print `n/a`; the aggregate means only
  cover measured rows (drift needs a beat-warp map, vocal and bass overlap need stems, low overlap needs separated
  contributions).
- [x] 4. Listening kit (below).
- [x] 5. Public-annotation accuracy: the M1H hooks (`mixconsole bench dataset ballroom|gtzan_rhythm|giantsteps_*
  --audio-dir DIR`) are unchanged and print acquisition instructions when audio/annotations are absent (checked). No
  such audio is on this machine, so no new numbers.
- [x] 6. This file; `scripts/check.sh` below.

## Corpus (licences)

All licences verified from the track pages on 2026-11-26 (FMA). "Genre" is the source's label, not ground truth. Gaps:
no CC0/CC-BY dancehall or genuine Bollywood film songs were found on FMA (Indian entries are Indian pop, devotional and
house); R&B is soul/downtempo. Many CC-BY tracks by "Alex Morgan" and similar are library-style instrumentals, so vocal
families are rarely exercised.

| id | artist | genre | licence |
|---|---|---|---|
| shivas_blossom | Koi-discovery | Indian / Bollywood house | CC0-1.0 |
| funky_pop | HoliznaCC0 | synth pop | CC0-1.0 |
| rock_and_roll | Rhapsody | rockabilly | CC0-1.0 |
| punk | HoliznaCC0 | punk rock | CC0-1.0 |
| free99 | OutPastMidnight | hip-hop vocal | CC0-1.0 |
| unwind | HoliznaCC0 | lo-fi hip-hop | CC0-1.0 |
| path | Metre | electronic dance | CC0-1.0 |
| dj_dance | Play House | house / EDM | CC0-1.0 |
| escape | Koi-discovery | rock | CC0-1.0 |
| open_up_your_eyes | Bob A. Feldman | acoustic folk | CC0-1.0 |
| lucidity | Soft and Furious | techno / synth pop | CC0-1.0 |
| razor_rock | Wax Lyricist | piano rock | CC0-1.0 |
| lets_bounce | 1000 Handz | EDM / house | CC-BY-4.0 |
| clone | 1000 Handz | EDM / house | CC-BY-4.0 |
| progressive_house_anthem | Alex Morgan | EDM / progressive house | CC-BY-4.0 |
| hot_amapiano_beats | Alex Morgan | afrobeats / amapiano | CC-BY-4.0 |
| final_chapter | 1000 Handz | hip-hop | CC-BY-4.0 |
| lost_and_found_1 | Purrple Cat | lo-fi hip-hop | CC-BY-4.0 |
| dance_dance | 1000 Handz | pop | CC-BY-4.0 |
| a_little_further | Pamela Yuen | pop | CC-BY-4.0 |
| cyberia | JMHBM | synth pop | CC-BY-4.0 |
| it_is_what_it_is | Neil Fernandes | rock | CC-BY-4.0 |
| justified | Neil Fernandes | rock | CC-BY-4.0 |
| release_for_joan | Mr Smith | rock | CC-BY-4.0 |
| soul_agent | Ketsa | R&B / soul | CC-BY-4.0 |
| happy_soul | Ketsa | R&B / soul | CC-BY-4.0 |
| bad_way | Pierce Murphy | R&B / soul | CC-BY-4.0 |
| afrobeast | Joseph Sacco | afrobeats | CC-BY-4.0 |
| amapiano_log_drum | Alex Morgan | afrobeats / amapiano | CC-BY-4.0 |
| sun_still_sky | Ketsa | afrobeat / downtempo | CC-BY-4.0 |
| indian_music_2 | Alex Morgan | Indian instrumental | CC-BY-4.0 |
| jadugar | Zahir | Indian pop | CC-BY-4.0 |
| patni | Zahir | Indian pop | CC-BY-4.0 |
| krishna_music_1 | Alex Morgan | Indian devotional pop | CC-BY-4.0 |
| mahamrityunjaya | Lopkerjo | Indian devotional | CC-BY-4.0 |
| beautiful_guitar_last_november | Matthew C. Wright | acoustic guitar | CC-BY-4.0 |
| calming_acoustic_guitar | Matthew C. Wright | acoustic guitar | CC-BY-4.0 |

## Results (8 of 36 pairs; budget 28 min)

Run: `mixconsole bench corpus --budget-minutes 28` on 2026-11-26, Apple M4. The budget stopped new pairs after 8:
edm_lets_bounce_clone, edm_path_lucidity, hiphop_final_chapter_lofi, pop_little_further_cyberia, rock_justified_joan,
rb_soul_agent_happy_soul, afro_afrobeast_log_drum, afro_sun_still_afrobeast. The other 28 are listed in LATEST.md as
not run. Seconds are inflated by the full `scripts/check.sh` running concurrently for part of the run.

| system | pass rate | dip LU | bump LU | peak dBTP | drift ms | low overlap bars | seconds/pair |
|---|---|---|---|---|---|---|---|
| linear6 | 0/8 | 3.57 | 0.48 | -0.02 | n/a | 0.08 | 1.3 |
| trim_eqpower | 0/8 | 1.29 | 1.45 | 0.10 | n/a | 0.16 | 1.0 |
| smooth | 8/8 | 0.22 | 0.56 | -1.05 | n/a | 0.12 | 64.6 |
| auto | 8/8 | 0.31 | 0.35 | -1.05 | 0.94 (n=2 of 8) | 0.13 | 62.7 |
| club | 8/8 | 0.31 | 0.25 | -1.05 | 0.95 (n=2 of 8) | 0.19 | 57.5 |

Full table (including vocal/bass overlap, clicks, fallback rate) is in `bench/results/LATEST.md`.
Families chosen: smooth 3 trim_crossfade / 3 echo_out / 2 cut_on_downbeat; auto 6 echo_out / 2 beatmatch_blend (drift
0.18 and 1.70 ms); club 6 echo_out / 1 beatmatch_blend / 1 stem_handoff (vocal and bass overlap 0, n=1). No pair needed the fallback.

automix-engine (2 pairs, separate result `2026-11-26-corpus-automix-engine-2pairs.json`): pass 2/2, dip 0.65 LU, peak
-0.99 dBTP, 174 s per pair, drift / overlap n/a (it exposes no stems or beat map to measure) versus `auto` 0.39 LU,
-1.05 dBTP, 36 s on the same two pairs.

Reading the numbers:
- The baselines fail the same verification gates that MixConsole is selected against (loudness dip over 1.5 LU and the
  -1 dBTP ceiling), so MixConsole's 100 % is partly by construction: it retries until a candidate passes, the
  baselines cannot. The comparison shows the cost of a naive crossfade, not that the mixes sound better. That is
  what the listening kit is for.
- 8 pairs and one run is a smoke-level sample. No confidence intervals are claimed for the objective table.
- Drift is only measured for beat-matched seams, so its mean covers 2 of 8 rows.

## Listening kit

`mixconsole listen build -o DIR [--input listen-input.json | --synthetic] [--challenger auto] [--embed]`
produces `DIR/index.html`, `DIR/audio/` (AAC 128k via ffmpeg, WAV when ffmpeg is absent) and `DIR/key.json`.
- Offline: no external script, font, link or analytics; no `fetch`/XHR; test-enforced. Votes live in browser
  localStorage and the rater presses "Save votes as JSON" (a local download). Put the files in `DIR/votes/`.
- Blind: audio files and items carry salted tokens, trial ids are tokenised, and the token to system map is only in
  `key.json`, which the page never loads. A/B sides are shuffled at build time (seeded); trial order is shuffled per rater.
- A/B: the challenger (default `auto`) against every other system, per pair; choices left / right / no preference.
- MUSHRA-lite: per pair a visible "Original" (A playing on, no mix), then every system plus a hidden reference (same audio
  under another token) and a hard-cut anchor, each rated 0 to 100.
- `mixconsole listen results DIR [votes...] [--no-screen]`: challenger win rate vs each baseline (tie = half a win) and
  MUSHRA means, each with a seeded 2000-sample percentile bootstrap 95 % CI; raters who give the hidden reference under 90
  in more than 15 % of sets are dropped from MUSHRA. Writes `results.json`/`results.md`; empty data prints `n/a`.
- Verified: structural tests, an end-to-end CLI test with simulated raters, and headless Chrome (page loads, buttons and
  sliders record votes to localStorage, no errors). A real kit from the 8 pairs is at `~/.cache/mixconsole/corpus/kit/`
  (64 clips, 41 MB). No humans have rated it yet, so there are no listening results.

## Limits

- 8 of 36 pairs run; genre coverage has gaps (above); some tracks are library instrumentals.
- No listening results; the objective metrics do not measure musicality.
- Baselines transition at the ends of the tracks; MixConsole picks cues anywhere, so excerpts differ in musical content.
- automix-engine: 2 pairs, needs about 3 GB of venv plus HF weights downloads, CPU/MPS heavy, seam position taken from its
  own report, so its overlap metrics are n/a.
- `club` aggregates for vocal and bass overlap rest on a single measured row.

## Final check

```
TOTAL                                           4629    337    93%

26 files skipped due to complete coverage.
Required test coverage of 91% reached. Total coverage: 92.72%
276 passed in 35.93s
scripts/check.sh  134.16s user 11.12s system 342% cpu 42.357 total
```
