#!/usr/bin/env python3
"""Rewrite requirements.txt as UTF-8 for Linux/pip (handles UTF-16/BOM/CRLF from Windows)."""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: normalize_requirements_for_docker.py <path>", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    b = path.read_bytes()
    if b.startswith(b"\xef\xbb\xbf"):
        b = b[3:]
    if b.startswith(b"\xff\xfe") or b.startswith(b"\xfe\xff"):
        enc = "utf-16-le" if b.startswith(b"\xff\xfe") else "utf-16-be"
        text = b.decode(enc).lstrip("\ufeff")
    elif b[:800].count(0) >= 4 and b"\x00" in b[:800]:
        try:
            text = b.decode("utf-16-le").lstrip("\ufeff")
        except UnicodeDecodeError:
            text = b.decode("utf-16-be").lstrip("\ufeff")
    else:
        text = b.decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
