# FocusWith Android Companion

The Android companion turns Android's usage-event access into the same `opened` / `closed` events used by iPhone Shortcuts. It also shows the active FocusWith timer in a persistent notification and, if the owner opts in, a small draggable overlay capsule.

## What it does

- Watches only the package names explicitly listed by the owner.
- Sends timestamped events through the phone-scoped `/api/phone/events` endpoint.
- Keeps a small on-device queue and retries after temporary network failures.
- Reads the active timer from `/api/phone/focus`, which does not expose projects, task notes, AI keys, or OAuth tokens.
- Shows the timer in a low-priority ongoing notification.
- Optionally shows a draggable timer capsule above other apps.

It cannot read screen pixels, messages, typed text, or content inside another app.

## Permissions

1. **Usage access — required.** Android exposes foreground/background package events through `UsageStatsManager`. This is a special Settings permission and must be enabled by the owner.
2. **Notifications — required while monitoring.** Android foreground services must remain visible to the user. The monitor therefore has an ongoing, low-priority notification.
3. **Display over other apps — optional.** This enables the floating timer capsule. It is off by default and monitoring continues normally without it.

The app intentionally does not request Accessibility, screen capture, contacts, messages, location, microphone, or the full Focus API token.

## Verify an official APK

Official GitHub release APKs are signed with this certificate SHA-256 fingerprint:

```text
14:75:E1:99:34:1B:16:F5:43:DF:7F:41:91:AB:A4:81:39:99:6B:50:70:4F:67:D5:BC:0C:72:DB:A9:3C:18:FB
```

The release also includes a `.sha256` file for verifying the downloaded APK bytes. Do not install an APK presented as an official FocusWith build if its signing certificate differs.

## Configure

1. Download the signed APK from [GitHub Releases](https://github.com/sayhi2e10414-cpu/focus-with/releases), install it, and open **FocusWith Companion**.
2. Enter the HTTPS origin of the FocusWith server, for example `https://focus.example.com`.
3. Enter `FOCUS_PHONE_TOKEN`, not `FOCUS_API_TOKEN`.
4. Edit monitored applications using one line per app:

   ```text
   小红书 | com.xingin.xhs
   抖音 | com.ss.android.ugc.aweme
   Instagram | com.instagram.android
   ```

5. Allow Usage access and notifications.
6. Optionally enable the overlay capsule.
7. Tap **Start monitoring**.

Some Android vendors aggressively stop background work. If events stop arriving, allow background activity for FocusWith and exclude it from vendor battery optimization. Force-stopping the app always stops monitoring until the owner opens it again.

## Build from source

The project uses platform Views and APIs only; it has no runtime library dependencies.

Requirements:

- JDK 17
- Android SDK 35
- Gradle 8.13

From the `android/` directory:

```bash
gradle :app:assembleDebug
```

The debug APK is created under `android/app/build/outputs/apk/debug/`. Version tags build a signed release APK through protected GitHub Actions secrets, verify its signature, and publish it with a SHA-256 checksum. The signing key must never be committed and must be backed up securely because future updates require the same key.
