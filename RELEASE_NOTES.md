# FocusWith v0.6.0 — Local Camera Companion

FocusWith can now notice when a phone remains in view during a focus session without sending camera frames away from the computer.

FocusWith 现在可以在专注时通过本机摄像头识别画面中的手机，同时不把摄像头画面发送到电脑之外。

## Highlights

- Added an opt-in Camera Companion to the native macOS FocusFloat window.
- Added local phone detection through Apple Vision and Core ML at about two frames per second.
- Added temporal smoothing: two positive frames confirm a phone, four misses are tolerated, and a reminder is eligible after ten sustained seconds.
- Added a 60-second local cooldown plus the existing server-side reminder cooldown and strike policy.
- Added a visible camera preview, detection state, one-click stop control, and macOS camera permission explanation.
- Added a platform-neutral, authenticated `/api/vision-events/phone` endpoint for future Windows and other native companions.

## Privacy and security

- Camera frames, crops, confidence values, bounding boxes, and embeddings stay inside FocusFloat.
- The server accepts only an event ID, sustained duration, timestamp, and client source. Unknown and image-derived fields are rejected.
- Event IDs are hashed for idempotency before storage.
- The Core ML model is downloaded from Apple's model assets during the first build and verified against a pinned SHA-256 checksum. It is not committed to the repository.
- Camera monitoring starts only after the owner presses **Start camera** and remains visibly indicated while active.

## Upgrade notes

- Existing SQLite installations are migrated automatically. The migration preserves existing phone-app intervention records while allowing camera-originated interventions.
- Existing web, phone, Android, AI, Telegram, and MCP behavior remains backward compatible.
- The included signed Android APK is versioned to 0.6.0 but does not add camera monitoring; Camera Companion is currently implemented on macOS.
- Windows can use the same server contract, but no Windows executable is included in this release.
- Back up the SQLite database or Docker volume before upgrading a production deployment.

See `docs/CAMERA_COMPANION.md`, `macos/FocusFloat/README.md`, `README.md`, `README.zh-CN.md`, and `SECURITY.md` before installation or public deployment.
