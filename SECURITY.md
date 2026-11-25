# Security policy

MixConsole is pre-alpha. Only the current development branch is supported; no
stable releases or security response time guarantees exist yet.

Report suspected vulnerabilities through GitHub's private vulnerability reporting
interface for this repository when available. Otherwise contact the maintainer
through a private method listed at [roop37](https://github.com/roop37), or open an
issue requesting a private channel without disclosing exploit details.

Include the affected revision, operating system, dependency versions, reproduction
steps and impact. Share only audio you have permission to distribute; a synthetic
fixture is preferred. Do not include credentials or personal data.

Audio parsing invokes native libraries and may invoke your installed ffmpeg. Keep
those dependencies updated and process untrusted files in an appropriately isolated
environment. MixScripts are validated data, not executable code. M0 does not fetch
audio, execute effect parameters, or download model weights.
