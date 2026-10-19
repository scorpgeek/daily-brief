"""The whole daily chain, unattended.

    extract -> brief -> build -> commit -> push

Every step but one is already a script. `brief` is the only one that needs
a model, and it lives in brief_ai.py behind the same command line.

    python daily.py                     # today's edition, newest PDF in inbox
    python daily.py --date 2026-10-20   # a specific issue
    python daily.py --pdf path\to.pdf
    python daily.py --no-push           # build and commit, do not publish
    python daily.py --skip-brief        # reuse an existing JSON brief

Set DB_API_KEY and DB_MODEL for the briefing step. With --skip-brief the
whole thing runs with no key at all, which is how it is exercised in CI
and how you can rehearse it before trusting it unattended.
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_raw")
INCOMING = os.path.join(HERE, "incoming")

PY = sys.executable


def run(*argv, capture=False) -> None:
    print(f"  $ {' '.join(os.path.basename(a) if a == PY else a for a in argv)}")
    r = subprocess.run(argv, cwd=HERE, capture_output=capture, text=True)
    if r.returncode != 0:
        if capture:
            sys.stdout.write(r.stdout or "")
            sys.stderr.write(r.stderr or "")
        sys.exit(f"step failed: {argv[0]} (exit {r.returncode})")
    if capture and r.stdout:
        for line in r.stdout.strip().splitlines():
            print(f"    {line}")


def newest_pdf(folder: str) -> str:
    hits = glob.glob(os.path.join(folder, "*.pdf"))
    if not hits:
        sys.exit(f"no PDF in {folder}")
    return max(hits, key=os.path.getmtime)


def git(*argv) -> None:
    r = subprocess.run(["git", *argv], cwd=HERE, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"git {' '.join(argv)} failed:\n{r.stderr.strip()}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="issue date, YYYY-MM-DD")
    ap.add_argument("--pdf", help="explicit PDF; default is the newest in the inbox")
    ap.add_argument("--folder", default=None, help="inbox to scan")
    ap.add_argument("--no-push", action="store_true", help="stop before publishing")
    ap.add_argument("--skip-brief", action="store_true",
                    help="reuse an existing JSON brief instead of calling a model")
    args = ap.parse_args()

    folder = args.folder or os.path.expanduser("~/Downloads/Telegram Desktop")
    if not os.path.isdir(INCOMING):
        os.makedirs(INCOMING, exist_ok=True)
    if args.pdf is None and not os.path.isdir(folder):
        folder = INCOMING

    pdf = args.pdf or newest_pdf(folder)
    stem = args.date or time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(pdf)))
    print(f"daily: {stem} from {os.path.basename(pdf)}\n")

    print("[1/5] extract")
    run(PY, os.path.join(HERE, "extract_pdf.py"), pdf)

    print("[2/5] brief")
    if args.skip_brief and os.path.exists(os.path.join(RAW, stem + ".json")):
        print(f"    reusing {stem}.json")
    else:
        run(PY, os.path.join(HERE, "brief_ai.py"), stem)

    print("[3/5] build")
    run(PY, os.path.join(HERE, "build_brief.py"), stem)

    print("[4/5] commit")
    git("add", "-A", "--", "phone.html", "desk.html", "archive", "incoming")
    if subprocess.run(["git", "diff", "--cached", "--quiet"],
                      cwd=HERE).returncode == 0:
        print("    nothing to commit")
    else:
        git("commit", "-q", "-m", f"Publish {stem}")
        print(f"    committed {stem}")

    if args.no_push:
        print("\n[5/5] publish — skipped (--no-push)")
        return
    print("[5/5] publish")
    git("push", "-q", "origin", "HEAD")
    print(f"    pushed. Pages serves it in about a minute, "
          f"plus up to ten minutes of cache.")


if __name__ == "__main__":
    main()