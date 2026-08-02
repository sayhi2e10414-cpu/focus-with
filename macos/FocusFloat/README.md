# FocusFloat for macOS

A small native floating timer for FocusWith. It stays above normal windows, follows the current session, and can pause, resume, or finish it.

It requires macOS 13 or later and Apple Command Line Tools, not the full Xcode app.

```bash
./macos/FocusFloat/install.sh
```

On first launch, enter the Focus URL and API token. The URL is stored in user preferences; the token is stored in the macOS Keychain and is never embedded in the app bundle.

## Camera Companion

Choose **Start camera** in the floating window to opt in. FocusFloat downloads Apple's YOLOv3 FP16 Core ML model on the first build, verifies its SHA-256 checksum, and runs detection through Vision/Core ML on the Mac.

- Inference runs locally at about two frames per second.
- Two positive frames confirm a phone; four misses are tolerated for changing angles.
- A reminder is eligible only after ten sustained seconds, with a 60-second local cooldown.
- The camera can remain on while FocusFloat is open, but the server creates a reminder only for a running work session.
- Frames, crops, confidence values, and bounding boxes are never sent to FocusWith. The API rejects those fields.

The camera indicator and preview remain visible while monitoring is on. Stop the camera from the same button or quit FocusFloat.

During a running work session, the camera companion sends a privacy-minimal
heartbeat about every 30 seconds so the floating window and reward system can
label uninterrupted time as camera verified. The heartbeat contains only time,
client source, and observing/stopped state. It contains no image-derived data;
see [the reward evidence rules](../../docs/REWARDS.md).

FocusFloat displays the selected reward and remaining uninterrupted time below
the timer. Without a current camera heartbeat, the server automatically labels
progress as timer + blocklist or timer only.

Run the native checks with:

```bash
./macos/FocusFloat/test.sh
```
