# HTTP API and projects (M4.5)

`mixconsole serve` starts a local FastAPI server over the same service facade the CLI uses
(`pip install 'mixconsole[server]'`, or the `ui` extra). It binds to `127.0.0.1` by default,
refuses a non-loopback bind without `--allow-remote`, checks the `Host` header (DNS-rebinding
guard) and requires a random per-run token on every route except `GET /api/v1/health`.

```sh
mixconsole serve --port 8765      # prints http://127.0.0.1:8765/api/v1 and the token
# token file: <data dir>/server.token (mode 0600); send "Authorization: Bearer <token>"
# or ?token=<token> (EventSource and <audio> cannot set headers)
```

Interactive docs are at `/docs`, the schema at `/openapi.json` (also committed as
`packages/schema-ts/openapi.json`, with generated TypeScript types in `packages/schema-ts`).

## Data layout

Default data dir: the platform user-data folder (`MIXCONSOLE_DATA_DIR`, `--data-dir`).

| Path | Content |
| --- | --- |
| `index.sqlite` | Library index: hash, paths, duration, BPM, key/Camelot, LUFS, energy summary, backend versions, scan failures |
| `jobs.sqlite` | Job rows and progress events (history survives restarts) |
| `projects/<id>/project.sqlite` | Tracks (file hash, original path), MixScript versions (append-only, `parent_id`), renders |
| `projects/<id>/artifacts/` | `analysis/<hash>.json+npz`, `peaks/<hash>/<spp>.json+.dat`, `previews/`, `renders/<id>/` |
| `server.token` | Token for the current server run |

A project folder is portable: database references are project-relative; only the original
audio paths are absolute (a track whose file moved reports `path_exists: false`).

## Uploads, stems and formats (M5)

- `POST /projects/{id}/uploads?name=song.flac` takes the raw audio as the request body (the browser
  console uses it for dropped files; at most 2 GiB, audio extensions only). The file is stored as
  `artifacts/uploads/<hash16>/<name>` and added to the project; the same content is deduplicated.
- `stems` (`off` | `auto` | `on`, default: the server setting) on `plans` and `mixes` overrides the
  `stems` setting for that job. Analysis processes keep the server setting.
- `format` (`wav` | `flac`) on `renders` chooses the container of the rendered file.

## Jobs

Long operations return `202` and a job: `analyze`, `plan`, `mix` (plan + verify + render),
`render` (a saved MixScript version) and `scan` (library folder). States are
`queued`, `running`, `done`, `failed`, `cancelled`. Progress events come from the service
facade (`stage`, `fraction`, `message`) and are stored; `GET /jobs/{id}/events` streams them as
Server-Sent Events (`progress`, then `end` with the final job; `Last-Event-ID` resumes) and
`GET /jobs/{id}/history` returns the same events as JSON. `POST /jobs/{id}/cancel` stops a
queued job at once and a running job at the next facade checkpoint. Concurrency is bounded by a
RAM budget (60 % of physical RAM unless `job_ram_mb` is set; analysis 1 GB, mix/render 2 GB
per job estimated; at least one job always runs).

## Artifacts for the UI

- `GET .../tracks/{hash}/waveform?resolution=256|1024|4096|16384`: audiowaveform JSON v2
  (8-bit min/max pairs, mono mix; samples per pixel at 44.1 kHz), directly usable by wavesurfer
  as peaks. `.../waveform.dat` is the same data in the binary audiowaveform format.
- `GET .../tracks/{hash}/lanes`: beats, downbeats, bars, phrases, sections, vocal spans and bar
  energy in seconds.
- `GET .../tracks/{hash}/preview` and `GET .../renders/{id}/files/{name}`: Opus (WAV when
  ffmpeg is missing) and report files with HTTP `Range` support (`206`, `416`).

## Editing

`POST .../mixscripts` validates a MixScript v1.1 document and appends it as a new version
(`parent_id` links it to what it was edited from; versions can never be updated or deleted).
`GET .../mixscripts/{id}/diff?against=<id>` lists JSON-pointer changes (default: against the
parent). Re-plan with `POST .../plans` (`parent_id`, `locks`).

## CLI

```text
mixconsole serve [--host 127.0.0.1] [--port 8765] [--data-dir DIR] [--cors-origin URL]
                 [--ui] [--ui-dir apps/console/dist]   # --ui also serves the built web console at /
mixconsole library scan DIR [--workers N]   # batch, parallel, resumable
mixconsole library list
```

`library scan` skips files whose path, size, mtime and backend versions match the index, and
commits after every batch, so killing and re-running it resumes where it stopped.
