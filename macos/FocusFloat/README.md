# FocusFloat

A small native macOS floating timer for Focus. It stays above normal windows, follows the current session, and can pause, resume, or finish it.

It requires macOS 13 or later and Apple Command Line Tools, not the full Xcode app.

```bash
./macos/FocusFloat/install.sh
```

On first launch, enter the Focus URL and API token. The URL is stored in user preferences; the token is stored in the macOS Keychain and is never embedded in the app bundle.
