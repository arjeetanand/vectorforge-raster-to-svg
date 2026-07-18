"""Small SVG document writer for editable closed paths."""

from __future__ import annotations

from html import escape
from typing import Iterable


def svg_document(width: int, height: int, paths: Iterable[tuple[str, str]]) -> str:
    """Create a standalone SVG; values are escaped even though colours are internal."""

    if width < 1 or height < 1:
        raise ValueError("SVG dimensions must be positive")
    body = "\n".join(
        f'  <path d="{escape(path, quote=True)}" fill="{escape(fill, quote=True)}" fill-rule="evenodd"/>'
        for path, fill in paths
        if path
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">\n'
        f"{body}\n</svg>\n"
    )
