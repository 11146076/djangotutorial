"""Compile locale/*.po → django.mo (Windows 無 GNU gettext 時使用)."""

from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parent.parent


def main():
    for po_path in (ROOT / "locale").rglob("django.po"):
        mo_path = po_path.with_suffix(".mo")
        polib.pofile(str(po_path)).save_as_mofile(str(mo_path))
        print(f"compiled {po_path.relative_to(ROOT)} → {mo_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
