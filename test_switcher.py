"""Where the newspaper switcher actually points.

The one thing that cannot be checked by eye is whether an archived
edition's switcher climbs back out of archive/ to reach the other
paper's alias. Both are the same markup with different hrefs, and the
depth is decided at build time, so a mistake here is silent: the link
renders fine and 404s only when someone taps it.
"""

import os
import re
import sys

FILES = [
    "hindu.html",
    "hindu-desk.html",
    "et.html",
    "et-desk.html",
    "archive/hindu-2026-10-19.html",
    "archive/hindu-2026-10-19-desk.html",
    "archive/et-2026-10-19.html",
    "archive/et-2026-10-19-desk.html",
]

HERE = os.path.dirname(os.path.abspath(__file__))
fail = 0

for name in FILES:
    path = os.path.join(HERE, name)
    if not os.path.exists(path):
        print(f"  MISSING  {name}")
        fail += 1
        continue
    src = open(path, encoding="utf-8").read()
    block = re.search(r'<details class="pnav"[^>]*>.*?</details>', src, re.S)
    if not block:
        print(f"  NO SWITCHER  {name}")
        fail += 1
        continue
    hrefs = re.findall(r'href="([^"]+)"', block.group(0))
    dead = [h for h in hrefs
            if not os.path.exists(os.path.normpath(
                os.path.join(os.path.dirname(path), h)))]
    mark = "FAIL" if dead else "ok"
    fail += 1 if dead else 0
    print(f"  {mark:<5} {name:<36} {len(hrefs)} links"
          + (f"  dead: {', '.join(dead)}" if dead else ""))

print("every switcher link resolves"
      if not fail else f"{fail} file(s) with broken switcher links")
sys.exit(1 if fail else 0)
