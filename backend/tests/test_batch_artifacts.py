from pathlib import Path

from app.services.batch_artifacts import (
    create_batch_zip,
    normalize_report_rows,
    report_bytes,
)
from app.services.presets import list_presets, preset_options


def test_presets_are_stable_and_return_copies():
    presets = list_presets()
    assert [item["id"] for item in presets] == [
        "signature-line-art",
        "flat-color-logo",
        "transparent-icon",
        "print-ready-artwork",
    ]
    options = preset_options("transparent-icon")
    options["color_count"] = 2
    assert preset_options("transparent-icon")["color_count"] == 8


def test_reports_are_deterministic_and_flatten_quality():
    rows = normalize_report_rows(
        [
            {
                "source_filename": "../logo.png",
                "status": "completed",
                "quality": {"score": 91, "path_count": 3},
            }
        ]
    )
    assert rows[0]["file"] == "logo.png"
    json_bytes, csv_bytes = report_bytes(
        [{"file": "logo.png", "status": "completed", "quality": {"score": 91}}]
    )
    assert b'"quality_score": 91' in json_bytes
    assert b"file,status,job_id" in csv_bytes


def test_zip_contains_reports_and_only_in_root_svg(tmp_path: Path):
    svg = tmp_path / "job" / "vector.svg"
    svg.parent.mkdir()
    svg.write_text('<svg viewBox="0 0 1 1"><path d="M0 0"/></svg>', encoding="utf-8")
    archive = create_batch_zip(
        tmp_path,
        [
            {"file": "../logo.png", "status": "completed", "svg_path": str(svg)},
            {
                "file": "failed.png",
                "status": "failed",
                "svg_path": str(tmp_path / "missing.svg"),
            },
        ],
    )
    import zipfile

    with zipfile.ZipFile(archive) as handle:
        assert set(handle.namelist()) == {"report.json", "report.csv", "svg/logo.svg"}
