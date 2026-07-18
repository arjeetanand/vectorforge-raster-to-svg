"""Safe report and ZIP creation for batch conversion workflows.

This module has no database or HTTP dependency so the batch API and CLI can
share it.  Paths are resolved under the supplied artifact root and archive
members are generated from sanitized source names, never from user-provided
path separators.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping


REPORT_FIELDS = (
    "file",
    "status",
    "job_id",
    "quality_score",
    "path_count",
    "retained_color_count",
    "removed_component_count",
    "model_used",
    "error_code",
)


def _safe_name(value: str, fallback: str = "asset") -> str:
    name = Path(value or fallback).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:180] or fallback


def normalize_report_rows(entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Flatten job/quality metadata into deterministic report rows."""

    rows: list[dict[str, Any]] = []
    for entry in entries:
        quality = entry.get("quality") or entry.get("diagnostics") or {}
        complexity = quality.get("svg_complexity") or {}
        rows.append(
            {
                "file": _safe_name(
                    str(entry.get("file") or entry.get("source_filename") or "asset")
                ),
                "status": str(entry.get("status", "unknown")),
                "job_id": str(entry.get("job_id") or entry.get("id") or ""),
                "quality_score": quality.get("score"),
                "path_count": quality.get("path_count"),
                "retained_color_count": quality.get("retained_color_count"),
                "removed_component_count": quality.get("removed_component_count"),
                "model_used": entry.get("model_used"),
                "error_code": entry.get("error_code"),
                "svg_complexity_level": complexity.get("level"),
            }
        )
    return rows


def report_bytes(entries: Iterable[Mapping[str, Any]]) -> tuple[bytes, bytes]:
    """Return UTF-8 JSON and CSV reports with stable key/column ordering."""

    rows = normalize_report_rows(entries)
    json_bytes = json.dumps(rows, indent=2, sort_keys=True).encode("utf-8")
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=REPORT_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return json_bytes, csv_buffer.getvalue().encode("utf-8")


def create_batch_zip(
    output_dir: str | Path,
    entries: Iterable[Mapping[str, Any]],
    archive_name: str = "vectorforge-results.zip",
) -> Path:
    """Write SVGs and JSON/CSV reports into one ZIP, skipping failed files."""

    root = Path(output_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    rows = list(entries)
    json_bytes, csv_bytes = report_bytes(rows)
    archive_path = root / _safe_name(archive_name, "vectorforge-results.zip")
    used: set[str] = set()
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.writestr("report.json", json_bytes)
        archive.writestr("report.csv", csv_bytes)
        for index, entry in enumerate(rows, start=1):
            svg_value = entry.get("svg_path")
            if not svg_value:
                continue
            svg_path = Path(str(svg_value)).resolve()
            if not svg_path.is_file() or svg_path.suffix.lower() != ".svg":
                continue
            # Include only files explicitly located inside this batch's root.
            try:
                svg_path.relative_to(root)
            except ValueError:
                continue
            base = _safe_name(str(entry.get("file") or svg_path.stem), f"asset-{index}")
            member = f"svg/{Path(base).stem}.svg"
            if member in used:
                member = f"svg/{Path(base).stem}-{index}.svg"
            used.add(member)
            archive.write(svg_path, member)
    return archive_path
