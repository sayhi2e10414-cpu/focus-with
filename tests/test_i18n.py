from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chinese_catalog_covers_static_ui_messages():
    app_source = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    index_source = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    catalog_source = (ROOT / "web" / "i18n.js").read_text(encoding="utf-8")

    used = set(re.findall(r'\bt\("((?:\\.|[^"\\])*)"', app_source))
    used.update(re.findall(r'data-i18n(?:-title|-aria-label)?="([^"]+)"', index_source))
    catalog = set(re.findall(r'^\s+"((?:\\.|[^"\\])*)":', catalog_source, flags=re.MULTILINE))

    assert used
    assert used <= catalog


def test_locale_switch_is_loaded_before_the_application():
    index_source = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert index_source.index("/assets/i18n.js") < index_source.index("/assets/app.js")
    assert 'data-action="switch-locale"' in index_source
    assert "focus_locale" in (ROOT / "web" / "i18n.js").read_text(encoding="utf-8")
