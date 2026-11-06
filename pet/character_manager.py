"""Loads installed character renderers from a local, trusted characters folder."""
import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def available_characters():
    result = {}
    for path in (ROOT / "characters").glob("*/character.json"):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
            if spec.get("renderer") == "qpainter" and isinstance(spec.get("id"), str):
                result[spec["id"]] = spec
        except (OSError, ValueError):
            continue
    return result


def load_character(char_id="chibi_boy"):
    specs = available_characters()
    if char_id not in specs:
        raise ValueError(f"Unknown character: {char_id}. Found: {list(specs)}")
    spec = specs[char_id]
    # Only import code from the character's own package, not an arbitrary JSON path.
    expected = f"characters.{char_id}.renderer"
    if spec.get("module") != expected or not char_id.isidentifier():
        raise ValueError("Unexpected renderer module in character.json")
    klass = getattr(importlib.import_module(expected), spec["class"])
    return spec, klass(spec)
