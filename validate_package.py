#!/usr/bin/env python3
import ast
import sys
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent
MODULES = (
    "pc_approval_matrix_v19",
    "pc_payment_request_v19",
    "pc_purchase_request_v19",
)


def validate_manifest(module):
    path = ROOT / module / "__manifest__.py"
    manifest = ast.literal_eval(path.read_text(encoding="utf-8"))
    assert manifest["version"].startswith("19.0."), path
    assert manifest.get("license"), path
    for relative in manifest.get("data", []):
        assert (ROOT / module / relative).is_file(), f"Missing {module}/{relative}"


def validate_python(module):
    for path in (ROOT / module).rglob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")


def validate_xml(module):
    for path in (ROOT / module).rglob("*.xml"):
        ElementTree.parse(path)


def main():
    for module in MODULES:
        assert (ROOT / module / "__init__.py").is_file(), module
        validate_manifest(module)
        validate_python(module)
        validate_xml(module)
    print("OK: manifests, referenced data files, Python syntax and XML syntax")
    return 0


if __name__ == "__main__":
    sys.exit(main())
