# FocusFloat for Windows

FocusFloat is an experimental native Windows companion for FocusWith. It keeps a
small timer window above other apps and can optionally use the webcam to detect a
cell phone locally. A phone must remain visible for ten seconds before the client
asks the FocusWith server to apply its normal reminder and strike policy.

## Current status

The source and automated build target Windows 10 version 2004 (build 19041) or
newer on x64 and ARM64. GitHub Actions compiles and tests the x64 build on
`windows-latest`. The maintainers do not currently have Windows camera hardware,
so camera selection, permission prompts, frame throughput, and real-world
detection accuracy still require validation on a physical Windows PC. Treat this
as a testable preview rather than a finished Windows release.

## Build

Install the [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) on a
Windows 10/11 computer, open PowerShell in the repository, and run:

```powershell
.\windows\FocusFloat\build.ps1
```

The script runs the portable unit tests, publishes a self-contained unpackaged
WinUI 3 app, and creates the archive plus its SHA-256 checksum:

```text
windows\FocusFloat\artifacts\FocusWith-Windows-win-x64.zip
windows\FocusFloat\artifacts\FocusWith-Windows-win-x64.zip.sha256
```

Extract the zip before running `FocusFloat.Windows.exe`. Windows may show a
SmartScreen warning because preview builds are not code-signed. The app uses the
Windows App SDK self-contained runtime, so users do not need to install the
Windows App Runtime separately.

To build ARM64 source instead:

```powershell
.\windows\FocusFloat\build.ps1 -Runtime win-arm64
```

## Connect

1. Start FocusWith and copy its main API token from the server's ignored `.env`
   file (`FOCUS_API_TOKEN`). The camera-only token is intentionally insufficient
   because the floating window also reads and controls the current timer.
2. Enter the FocusWith base URL, such as `http://127.0.0.1:8765/`.
3. Enter the token and select **Connect and save**.
4. Select **Start camera** and approve the Windows camera permission if prompted.

The server URL is stored in
`%LOCALAPPDATA%\FocusWith\FocusFloat\settings.json`. The token is stored through
Windows Credential Locker, not in that JSON file.

## Local model

On first camera start the app downloads the pinned ONNX Model Zoo YOLOv3-10
model (about 236 MB) into:

```text
%LOCALAPPDATA%\FocusWith\FocusFloat\Models\yolov3-10.onnx
```

It verifies SHA-256
`1f4613c3d04416dfd2c1960b8737aa5292994238dfecbe9c1ee7147e9a92439f`
before loading it. You can also download and verify the same model manually:

```powershell
.\windows\FocusFloat\download-model.ps1
```

The model file is intentionally excluded from Git and from build artifacts.

## Privacy and behavior

- Camera use starts only after clicking **Start camera**, stays visibly marked
  with `CAMERA ON`, and stops with one click or when the app closes.
- Frames are processed in memory by ONNX Runtime and are not saved or uploaded.
- No image, crop, confidence score, embedding, or bounding box is sent.
- Only event ID, sustained duration, UTC timestamp, and
  `windows_focus_float` source may reach the FocusWith server.
- The app needs two detection hits to confirm a phone, tolerates four misses,
  requires ten sustained seconds, and applies a 60-second local cooldown.
- An event is sent only while FocusWith reports a running, non-break session.

See [the shared camera contract](../../docs/CAMERA_COMPANION.md) and
[third-party notices](THIRD_PARTY_NOTICES.md).
