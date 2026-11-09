"""Colour tables of the gate rules, read from the .lp files so the test fixtures follow them."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def layer_colors() -> dict:
    """band -> {"fillColor": .., "strokeColor": ..} from asp/gate3/colors.lp."""
    text = (ROOT / "asp/gate3/colors.lp").read_text(encoding="utf-8")
    colors = {}
    for band, key, value in re.findall(r'layer_color\((\w+),\s*"(\w+)",\s*"([^"]+)"\)\.', text):
        colors.setdefault(band, {})[key] = value
    return colors


def frame_colors() -> dict:
    """band -> (label, stroke, fill) from asp/gate3/bands.lp."""
    text = (ROOT / "asp/gate3/bands.lp").read_text(encoding="utf-8")
    return {band: (label, stroke, fill) for band, label, stroke, fill in
            re.findall(r'band_frame\((\w+),\s*"[^"]+",\s*"([^"]+)",\s*"([^"]+)",\s*"([^"]+)"\)\.', text)}


def element_style(band: str) -> str:
    """Colour part of a correct vertex style for an element of the band."""
    c = layer_colors()[band]
    return f"fillColor={c['fillColor']};strokeColor={c['strokeColor']};" + ("dashed=1;" if band == "other" else "")
