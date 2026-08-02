import plistlib
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_versions_stay_in_sync():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    android = (ROOT / "android/app/build.gradle.kts").read_text(encoding="utf-8")
    windows = (
        ROOT / "windows/FocusFloat/FocusFloat.Windows/FocusFloat.Windows.csproj"
    ).read_text(encoding="utf-8")
    with (ROOT / "macos/FocusFloat/Info.plist").open("rb") as handle:
        macos = plistlib.load(handle)

    assert pyproject["project"]["version"] == version
    assert re.search(rf'versionName = "{re.escape(version)}"', android)
    assert f"<Version>{version}</Version>" in windows
    assert macos["CFBundleShortVersionString"] == version


def test_release_workflow_publishes_android_and_windows_checksums():
    workflow = (ROOT / ".github/workflows/android-release.yml").read_text(
        encoding="utf-8"
    )

    assert "needs: [android, windows]" in workflow
    assert "runs-on: windows-latest" in workflow
    assert "FocusWith-Android-${{ github.ref_name }}.apk.sha256" in workflow
    assert "FocusWith-Windows-win-x64.zip.sha256" in workflow
    assert "sha256sum --check" in workflow
    assert 'release_title="$(sed -n' in workflow
    assert "--prerelease" in workflow
