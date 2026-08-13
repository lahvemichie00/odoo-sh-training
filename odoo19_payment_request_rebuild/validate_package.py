#!/usr/bin/env python3
"""Static checks that do not require an Odoo server runtime."""

import ast
import csv
import sys
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent
errors = []


def fail(path, message):
    errors.append(f"{path.relative_to(ROOT)}: {message}")


for path in sorted(ROOT.rglob("*.py")):
    try:
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except Exception as exc:  # pragma: no cover - command-line validation
        fail(path, f"invalid Python: {exc}")

for path in sorted(ROOT.rglob("*.xml")):
    try:
        ElementTree.parse(path)
    except Exception as exc:  # pragma: no cover - command-line validation
        fail(path, f"invalid XML: {exc}")

for manifest_path in sorted(ROOT.glob("*/__manifest__.py")):
    try:
        manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("installable"):
            fail(manifest_path, "addon is not installable")
        for relative_path in manifest.get("data", []):
            target = manifest_path.parent / relative_path
            if not target.is_file():
                fail(manifest_path, f"missing data file: {relative_path}")
    except Exception as exc:  # pragma: no cover - command-line validation
        fail(manifest_path, f"invalid manifest: {exc}")

for path in sorted(ROOT.rglob("*.csv")):
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.reader(stream)
            rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not rows:
            fail(path, "empty CSV")
            continue
        width = len(rows[0])
        for line_number, row in enumerate(rows[1:], start=2):
            if len(row) != width:
                fail(path, f"line {line_number} has {len(row)} columns; expected {width}")
    except Exception as exc:  # pragma: no cover - command-line validation
        fail(path, f"invalid CSV: {exc}")

if errors:
    print("VALIDATION FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("VALIDATION PASSED")
print("- Python syntax")
print("- XML syntax")
print("- Manifest data paths")
print("- CSV column consistency")
