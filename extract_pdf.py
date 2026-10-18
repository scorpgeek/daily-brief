"""
Daily newspaper extractor.

Pulls text out of a newspaper PDF (Economic Times, Mint, etc.) and drops it
into a dated .txt file so it can be fed into the daily digest build.

Usage
-----
    python extract_pdf.py                       # newest PDF in the inbox folder
    python extract_pdf.py "path/to/file.pdf"    # explicit file
    python extract_pdf.py --folder "D:\\News"    # custom inbox
    python extract_pdf.py --out-dir "C:\\raw"   # custom output folder

Inbox defaults to the Telegram Desktop downloads folder, which is where the
daily copy normally lands. Files are picked by modification time, newest first,
so re-running on the same day just overwrites today's extract.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import sys
from datetime import datetime

try:
    from pypdf import PdfReader
except ImportError:
    sys.exit("pypdf not installed. Run:  python -m pip install pypdf")

# The magazine PDF carries many subsetted Type1 fonts. pypdf chatters loudly
# about missing fontTools on every one of them; none of it affects extraction.
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf._cmap").setLevel(logging.ERROR)
logging.getLogger("pypdf.generic").setLevel(logging.ERROR)

DEFAULT_INBOX = os.path.expanduser(
    r"~\Downloads\Telegram Desktop"
)

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUT = os.path.join(HERE, "_raw")

PAGE_MARKER = re.compile(r"^===== PAGE (\d+) =====$", re.M)


def pick_newest_pdf(folder: str) -> str:
    """Newest .pdf in the folder. Filenames here contain superscript unicode
    (e.g. "ET Magazine 18102026") which the shell mangles, so this always
    globs rather than trusting a typed path."""
    matches = glob.glob(os.path.join(folder, "*.pdf"))
    if not matches:
        sys.exit(f"No PDF found in {folder}")
    return max(matches, key=os.path.getmtime)


def extract(path: str) -> str:
    reader = PdfReader(path)
    chunks = [f"===== PAGE {i} =====\n{page.extract_text() or ''}"
              for i, page in enumerate(reader.pages, 1)]
    return "\n\n".join(chunks)


def date_label(path: str) -> str:
    """Pull a YYYYMMDD out of the filename if there is one, else use mtime."""
    stem = os.path.splitext(os.path.basename(path))[0]
    m = re.search(r"(\d{4})(\d{2})(\d{2})", stem)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime(y, mo, d).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract text from a newspaper PDF.")
    ap.add_argument("pdf", nargs="?", help="PDF path. Omit to use the newest in the inbox.")
    ap.add_argument("--folder", default=DEFAULT_INBOX, help="Inbox folder to scan.")
    ap.add_argument("--out-dir", default=DEFAULT_OUT, help="Where to write the .txt.")
    args = ap.parse_args()

    path = args.pdf or pick_newest_pdf(args.folder)
    print(f"source : {path}")

    text = extract(path)
    pages = len(PAGE_MARKER.findall(text))

    os.makedirs(args.out_dir, exist_ok=True)
    dest = os.path.join(args.out_dir, f"{date_label(path)}.txt")
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(f"SOURCE: {path}\nEXTRACTED: {datetime.now():%Y-%m-%d %H:%M}\n")
        fh.write(f"PAGES: {pages}  CHARS: {len(text)}\n")
        fh.write("=" * 60 + "\n")
        fh.write(text)

    print(f"pages  : {pages}")
    print(f"chars  : {len(text):,}")
    print(f"written: {dest}")


if __name__ == "__main__":
    main()