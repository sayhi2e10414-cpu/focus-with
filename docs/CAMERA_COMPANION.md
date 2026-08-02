# Camera Companion

FocusWith supports opt-in camera companions that detect a phone locally and send only a small distraction event to the Focus server. The included macOS FocusFloat client is the reference implementation, and an experimental Windows implementation is available for hardware testing.

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

## Reward evidence heartbeat

When uninterrupted-focus rewards are enabled, an active companion also sends a
three-field heartbeat about every 30 seconds:

```json
{
  "observed_at": "2026-08-02T09:00:00Z",
  "source": "windows_focus_float",
  "camera_state": "observing"
}
```

`POST /api/vision-events/heartbeat` rejects unknown fields and keeps only the
latest heartbeat time and source for the active session. It receives no image or
image-derived result. If the heartbeat expires, reward accounting automatically
falls back to timer + blocklist or timer-only mode. See
[REWARDS.md](REWARDS.md).

## macOS

See [macos/FocusFloat/README.md](../macos/FocusFloat/README.md). The included client uses AVFoundation, Vision, and Core ML. Its model is downloaded from Apple's model assets during the first build and is not committed to this repository.

## Windows

See [windows/FocusFloat/README.md](../windows/FocusFloat/README.md). The
experimental WinUI 3 client uses `MediaFrameReader`, ONNX Runtime, a
checksum-pinned YOLOv3 model, Windows Credential Locker, and the same temporal
rules as the macOS client. Its contract test proves that Windows events contain
exactly the four documented fields.

The x64 source is compiled and tested by `windows-latest` CI, but real camera
permission, selection, throughput, and detection accuracy have not yet been
validated on physical Windows hardware. The server endpoint is already
platform-neutral and does not require a server upgrade.
