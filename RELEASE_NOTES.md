# FocusWith v0.7.0 — Rewards & Windows Preview

FocusWith now turns uninterrupted focus time into rewards you choose, and the
native floating companion is available as an experimental Windows download.

FocusWith 现在可以把不间断专注时间兑换成自己设定的奖励，同时提供实验性的
Windows 原生悬浮窗下载。

## Highlights

- Added editable rewards with a default example, selectable targets, persistent
  earned inventory, and explicit redemption.
- Added camera-verified, timer-plus-blocklist, and pure-timer evidence modes with
  automatic fallback when a camera companion is unavailable.
- Added reward countdowns to the Web UI and the macOS and Windows floating
  companions.
- Added four scoped reward tools to Local MCP and OAuth-protected Remote MCP.
- Added an experimental self-contained Windows x64 companion with a floating
  timer, Windows Credential Locker storage, local ONNX phone detection, and
  privacy-minimal distraction reporting.

## Windows preview status

- The Windows app is compiled and tested on GitHub's `windows-latest` runner.
- It targets Windows 10 version 2004 (build 19041) or newer on x64.
- No physical Windows camera has been available to the maintainers yet, so
  camera selection, permission prompts, frame throughput, and real-world
  detection accuracy still need tester feedback.
- The ZIP is not code-signed, so Windows SmartScreen may warn before first run.
- Extract `FocusWith-Windows-win-x64.zip`, then run
  `FocusFloat.Windows.exe`.
- The first camera start downloads the pinned YOLOv3 ONNX model (about 236 MB)
  and verifies its SHA-256 checksum.

## Privacy and security

- Camera frames, crops, confidence values, bounding boxes, and embeddings stay
  on the companion device.
- Reward heartbeats contain only UTC time, client source, and observing/stopped
  state.
- Sustained-phone events contain only an event ID, duration, timestamp, and
  client source.
- Image-derived fields are rejected by the server.
- Camera monitoring is opt-in and visibly marked while active.
- The Windows token is stored with Windows Credential Locker.

## Downloads

- `FocusWith-Android-v0.7.0.apk` — signed Android companion.
- `FocusWith-Windows-win-x64.zip` — experimental unsigned Windows companion.
- Verify either download with its adjacent `.sha256` file.

## Upgrade notes

- Existing SQLite installations are migrated automatically.
- Existing web, Android, phone, AI, Telegram, and MCP behavior remains backward
  compatible.
- Back up the SQLite database or Docker volume before upgrading a production
  deployment.

See `docs/REWARDS.md`, `docs/CAMERA_COMPANION.md`,
`windows/FocusFloat/README.md`, `README.md`, `README.zh-CN.md`, and
`SECURITY.md` before installation or public deployment.
