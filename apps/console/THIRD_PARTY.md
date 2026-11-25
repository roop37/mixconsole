# Web console third-party packages

Direct dependencies of `apps/console` (exact versions are pinned in `package.json` and `pnpm-lock.yaml`).
The Python registry stays in the root `THIRD_PARTY.md`. Everything is bundled by Vite at build time:
the served app loads no external script, stylesheet, font or CDN asset.

| Package | Version | License | Use | URL |
| --- | --- | --- | --- | --- |
| react | 19.2.9 | MIT | UI runtime | [npm](https://www.npmjs.com/package/react/v/19.2.9) |
| react-dom | 19.2.9 | MIT | UI runtime | [npm](https://www.npmjs.com/package/react-dom/v/19.2.9) |
| wavesurfer.js | 7.12.12 | BSD-3-Clause | Waveform and transport | [npm](https://www.npmjs.com/package/wavesurfer.js/v/7.12.12) |
| vite | 7.3.8 | MIT | Build (dev) | [npm](https://www.npmjs.com/package/vite/v/7.3.8) |
| @vitejs/plugin-react | 5.2.0 | MIT | Build (dev) | [npm](https://www.npmjs.com/package/@vitejs/plugin-react/v/5.2.0) |
| typescript | 5.9.3 | Apache-2.0 | Type checking (dev) | [npm](https://www.npmjs.com/package/typescript/v/5.9.3) |
| vitest | 3.2.7 | MIT | Unit tests (dev) | [npm](https://www.npmjs.com/package/vitest/v/3.2.7) |
| @playwright/test | 1.65.1 | Apache-2.0 | Browser smoke test (dev) | [npm](https://www.npmjs.com/package/@playwright/test/v/1.65.1) |
| @biomejs/biome | 2.6.9 | MIT OR Apache-2.0 | Lint and format (dev) | [npm](https://www.npmjs.com/package/@biomejs/biome/v/2.6.9) |
| @types/react, @types/react-dom, @types/node | 19.3.3, 19.3.0, 24.19.4 | MIT | Types (dev) | [npm](https://www.npmjs.com/org/types) |
