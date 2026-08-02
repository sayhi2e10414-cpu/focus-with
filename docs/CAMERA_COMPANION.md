# Camera Companion

FocusWith supports opt-in camera companions that detect a phone locally and send only a small distraction event to the Focus server. The included macOS FocusFloat client is the reference implementation.

## Privacy boundary

The companion owns camera capture and inference. A frame must not leave the device. The server endpoint intentionally accepts only:

```json
{
  "event_id": "a-client-generated-id",
  "duration_seconds": 10,
  "detected_at": "2026-08-02T09:00:00Z",
  "source": "macos_focus_float"
}
```

`POST /api/vision-events/phone` uses the normal `X-Focus-Token` header. Unknown properties are rejected, so images, crops, confidence values, embeddings, and bounding boxes cannot be added accidentally.

The event ID makes retries idempotent. `duration_seconds` is limited to 10–300 seconds. The server clamps timestamps with more than five minutes of clock drift, ignores events without a running work session, and applies the configured reminder cooldown and strike policy.

A successful response looks like:

```json
{
  "success": true,
  "data": {
    "accepted": true,
    "reason": "notified",
    "intervention_id": 42,
    "strike": 1
  }
}
```

`accepted` can be false with `no_running_focus` or `cooldown`. Sending the same event again returns `duplicate` and does not create a second notification.

## macOS

See [macos/FocusFloat/README.md](../macos/FocusFloat/README.md). The included client uses AVFoundation, Vision, and Core ML. Its model is downloaded from Apple's model assets during the first build and is not committed to this repository.

## Windows adapter

The server contract is already platform-neutral. No Windows executable is included yet; the native client remains a separate, test-on-Windows implementation. It should use:

- [`MediaCapture`](https://learn.microsoft.com/windows/apps/develop/camera/basic-photo-capture) or `MediaFrameReader` for visible, opt-in camera capture.
- [Windows ML](https://learn.microsoft.com/windows/ai/new-windows-ml/overview) or [ONNX Runtime](https://onnxruntime.ai/docs/get-started/with-windows.html) for local object detection.
- The same temporal rules as FocusFloat: two hits to confirm, four misses tolerated, ten sustained seconds, and a 60-second local cooldown.
- Windows Credential Manager for the Focus API token.
- A persistent camera-on indicator and one-click stop control.

The ONNX model and preprocessing must be pinned by URL, license, version, and SHA-256 checksum. A Windows client must pass contract tests proving its JSON contains exactly the four documented properties before it is presented as supported. The server-side endpoint does not require a server upgrade when that client is added.
