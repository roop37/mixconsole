## Native libraries and optional models

The allowlist covers distribution metadata (including dev/docs/all optional lock
entries). It is not an exhaustive scanner of bundled native source notices.
Keep the license files shipped with all wheels. Legacy ambiguous metadata is
reviewed in version-bound overrides in `scripts/third_party.py`; unknown versions
fail until reviewed. Snapshot refresh uses installed metadata, or versioned PyPI
metadata for absent extras; CPU torch uses its upstream release metadata.

- **SoundFile / libsndfile**: BSD-3-Clause wrapper dynamically loads libsndfile
  (LGPL-2.1-or-later) using CFFI. The shared library can be replaced by the user.
  [Upstream](https://libsndfile.github.io/libsndfile/).
- **soxr / libsoxr**: LGPL-2.1-or-later. Python dynamically loads the replaceable
  `soxr_ext` extension. `otool -L` on the macOS wheel shows system libraries only:
  libsoxr is embedded inside that shared extension, not a separate dylib. MixConsole
  links to neither; users can replace/rebuild the complete extension from
  [source](https://github.com/dofuuz/python-soxr). No copyleft source is copied.
- **libsndfile codecs**: libFLAC, libogg/libvorbis use BSD-3-Clause; optional
  libmpg123 uses LGPL-2.1-or-later. Wheel/system build determines components.
  [FLAC](https://xiph.org/flac/license.html), [Xiph](https://www.xiph.org/licenses/),
  [mpg123](https://www.mpg123.de/).
- **NumPy/SciPy/llvmlite**: bundled OpenBLAS/LAPACK (BSD-3-Clause), LLVM
  (Apache-2.0 WITH LLVM-exception) and, on some platforms, GCC runtime libraries
  (GPL-3.0-or-later WITH GCC-exception-3.1). Runtime exceptions and bundled notices
  apply independently of the Python distribution's license field.
  [LLVM](https://llvm.org/docs/DeveloperPolicy.html#license),
  [GCC runtime exception](https://www.gnu.org/licenses/gcc-exception-3.1.html).
- **torch** is optional. The uv lock uses CPU wheels on Linux/Windows and macOS
  wheels on Darwin; no NVIDIA EULA distributions remain in the lock. Its upstream
  BSD-3-Clause metadata does not replace bundled notices (including Apache, LLVM,
  BSD, BSL-1.0, ISC, MIT and Zlib components). BSL-1.0 is a narrow, reviewed
  exception to the distribution allowlist for optional torch only; unknown
  packages or versions still fail the gate. Core installs contain no torch.
  Source routing is uv-specific; pip users must select the CPU index explicitly.
  [CPU installation](https://docs.astral.sh/uv/guides/integration/pytorch/),
  [torch license](https://github.com/pytorch/pytorch/blob/main/LICENSE).
- **Beat This!** code and published `final0` checkpoint: MIT. The optional model
  manager fetches the official checkpoint into the ignored MixConsole cache from
  [CPJKU](https://cloud.cp.jku.at/public.php/dav/files/7ik4RrBKTS273gp/final0.ckpt)
  and verifies SHA-256
  `8c328b45f59d8dd3dff219253ff6a8d6482be57d0133a29140e2febbf8eb8331`.
  No weights are bundled. Users can override the checkpoint path; its hash enters
  analysis provenance. [License](https://github.com/CPJKU/beat_this#license).
- **Demucs htdemucs** (stems extra, M3): Demucs code (`demucs` 4.1.0) and the
  published `htdemucs` weights (signature `955717e8`) are MIT-licensed by Meta
  Platforms ([LICENSE](https://github.com/facebookresearch/demucs/blob/main/LICENSE);
  the README states that the code and models are released under MIT). The optional
  model manager fetches `955717e8-8726e21a.th` from
  [dl.fbaipublicfiles.com](https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/955717e8-8726e21a.th)
  into the ignored MixConsole cache and verifies SHA-256
  `8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4`. No weights
  are bundled. The training data (MUSDB18-HQ plus 800 licensed songs) is not
  redistributed. Only `demucs.apply`/`demucs.pretrained` are imported;
  demucs' I/O helpers `lameenc` (LGPL-3.0, MP3 encoder) and `sphn` (no licence
  metadata) are excluded from the lock via uv `override-dependencies` and never
  loaded. Intel macOS is not supported for stems (demucs pins torch<2.3 there).
- **All-In-One**: reserved stub, never executed/installed by an extra. Upstream
  code MIT; NATTEN/madmom constraints require a separate review before enabling.
  [Upstream](https://github.com/mir-aidj/all-in-one).
- **Signalsmith Stretch / python-stretch 0.3.1**: the MIT-licensed Python
  binding includes the MIT-licensed Signalsmith Stretch C++ library. It is the
  M2 core time stretcher. The binding and native source licenses are at
  [python-stretch](https://github.com/gregogiudici/python-stretch/blob/main/LICENSE)
  and [Signalsmith Stretch](https://github.com/Signalsmith-Audio/signalsmith-stretch/blob/main/LICENSE.txt).
  No Rubber Band library is linked or copied.
- **ffmpeg**: optional external system process; LGPL/GPL depending on build,
  neither linked nor distributed. [Terms](https://ffmpeg.org/legal.html).

## Development and external tools

Hatchling and its Python build dependencies are in the lock table. uv (MIT OR
Apache-2.0), Node.js (MIT plus bundled notices), the Pyright runtime (MIT),
GitHub actions/checkout and upload-artifact (MIT), setup-uv (MIT OR Apache-2.0),
CodeQL action (MIT), lychee/lychee-action (MIT OR Apache-2.0 / MIT), and
markdownlint-cli2 / its action (MIT) are developer tools, not audio-engine dependencies.

[uv](https://github.com/astral-sh/uv), [Node](https://github.com/nodejs/node),
[Pyright](https://github.com/microsoft/pyright), [checkout](https://github.com/actions/checkout),
[upload-artifact](https://github.com/actions/upload-artifact),
[setup-uv](https://github.com/astral-sh/setup-uv),
[CodeQL action](https://github.com/github/codeql-action),
[lychee](https://github.com/lycheeverse/lychee),
[lychee action](https://github.com/lycheeverse/lychee-action),
[markdownlint](https://github.com/DavidAnson/markdownlint-cli2),
[markdownlint action](https://github.com/DavidAnson/markdownlint-cli2-action).

Dataset manifests describe annotation sources and separate audio rights; they are
not dependencies or redistributed datasets. No audio, model weights, NATTEN or
madmom implementation is distributed. Key profiles are published numeric parameters
and an original triadic profile, not copied code or model weights.
- **automix-engine** (optional external benchmark baseline, M4): LGPL-2.1,
  [VertexSelection/automix-engine](https://github.com/VertexSelection/automix-engine). Never a
  dependency: `scripts/setup_automix_engine.sh` clones it into the ignored cache with its own
  venv and `mixconsole bench corpus --systems ...,automix_engine` runs it only as a separate
  process. Nothing is imported, vendored or redistributed.
