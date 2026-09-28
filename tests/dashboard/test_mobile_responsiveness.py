from __future__ import annotations

from pathlib import Path
import re
import pytest

WEB_ROOT = Path(__file__).resolve().parents[2] / "operator_dashboard" / "web"
STYLES_CSS = WEB_ROOT / "src" / "styles.css"
REPLAY_CANVAS = WEB_ROOT / "src" / "components" / "ReplayCanvas.tsx"
REPLAY_CONTROLLER = WEB_ROOT / "src" / "components" / "ReplayController.tsx"
REPLAY_SECTORS = WEB_ROOT / "src" / "components" / "ReplaySectorMetrics.tsx"


def test_styles_css_overflow_guards():
    assert STYLES_CSS.is_file(), "styles.css must exist"
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert "overflow-x: hidden" in css
    # Check body and main overflow-x: hidden
    assert re.search(r"body\s*\{[^}]*overflow-x:\s*hidden", css)
    assert re.search(r"main\s*\{[^}]*overflow-x:\s*hidden", css)


def test_map_wrap_responsive_height():
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert "clamp(300px, 50vh, 480px)" in css


def test_clock_clamp_responsive():
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert "clamp(1.5rem, 6vw, 2.4rem)" in css


def test_touch_target_sizes_in_css():
    css = STYLES_CSS.read_text(encoding="utf-8")
    # Scrubber thumb at least 22px
    assert "22px" in css
    assert re.search(r"slider-thumb\s*\{[^}]*min-width:\s*22px", css)
    assert re.search(r"slider-thumb\s*\{[^}]*min-height:\s*22px", css)

    # Replay buttons >= 40-44px
    assert re.search(r"\.replay-btn\s*\{[^}]*min-height:\s*42px", css)

    # Speed pills >= 36px
    assert re.search(r"\.replay-speed-btn\s*\{[^}]*min-height:\s*36px", css)

    # Legend buttons comfortable touch height >= 36px
    assert re.search(r"\.legend-btn\s*\{[^}]*min-height:\s*(36|38)px", css)


def test_speed_pills_mobile_layout():
    css = STYLES_CSS.read_text(encoding="utf-8")
    # Speed selector on mobile wraps into 2-row layout or scrollable pill bar
    assert "replay-speed-pills" in css
    assert re.search(r"grid-template-columns:\s*repeat\(4,\s*1fr\)", css) or "overflow-x: auto" in css


def test_sector_metrics_2_column_mobile():
    css = STYLES_CSS.read_text(encoding="utf-8")
    # < 640px 2-column grid
    m = re.search(r"@media\s*\(\s*max-width:\s*640px\s*\)\s*\{([\s\S]*?)\n\}", css)
    assert m is not None, "media query 640px must exist"
    media_block = m.group(1)
    assert re.search(r"\.replay-sectors-grid\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*1fr\)", media_block)


def test_main_padding_mobile():
    css = STYLES_CSS.read_text(encoding="utf-8")
    # < 600px main padding 0.75rem 0.5rem
    m = re.search(r"@media\s*\(\s*max-width:\s*600px\s*\)\s*\{([\s\S]*?)\n\}", css)
    assert m is not None, "media query 600px must exist"
    media_block = m.group(1)
    assert re.search(r"main\s*\{[^}]*padding:\s*0\.75rem\s+0\.5rem", media_block)


def test_replay_canvas_high_dpi():
    assert REPLAY_CANVAS.is_file(), "ReplayCanvas.tsx must exist"
    code = REPLAY_CANVAS.read_text(encoding="utf-8")
    assert "devicePixelRatio" in code
    assert "ctx.scale(dpr, dpr)" in code
    assert "canvas.width = targetW" in code
    assert "canvas.height = targetH" in code
    assert "addEventListener(\"resize\"" in code
