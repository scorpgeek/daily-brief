"""Check that build_brief.py rejects briefs it should reject.

    python test_build.py

A brief is hand-written every day, so these guards are the only thing
standing between a typo in the JSON and a silently broken edition.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build_brief.py")

def _strip_watchfor(d):
    d = json.loads(json.dumps(d))
    for it in d["top"]:
        if it["tag"] == "WATCH":
            it.pop("watchFor", None)
    return d


def _bad_tag(d):
    d = json.loads(json.dumps(d))
    d["top"][0]["tag"] = "URGENT"
    return d


CASES = [
    ("missing date", None, "does-not-exist"),
    ("no top section", lambda d: {k: v for k, v in d.items() if k != "top"}, "no-top"),
    ("WATCH without watchFor", _strip_watchfor, "no-watchfor"),
    ("bad tag", _bad_tag, "bad-tag"),
]


def run(stem, data=None):
    if data is not None:
        p = os.path.join(tempfile.mkdtemp(), stem + ".json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        target = p
    else:
        target = stem
    r = subprocess.run([sys.executable, BUILD, target, "--desk"],
                       capture_output=True, text=True)
    out = (r.stdout + r.stderr).strip().splitlines()
    tail = out[-1] if out else "(no output)"
    return r.returncode, tail


base = json.load(open(os.path.join(HERE, "_raw", "2026-10-19.json"),
                     encoding="utf-8"))

print(f"{'case':<26} exit  message")
print("-" * 78)
fails = 0
for name, fn, stem in CASES:
    code, msg = run(stem, fn(base) if fn else None)
    ok = code != 0
    fails += 0 if ok else 1
    print(f"{name:<26} {code:<5} {msg[:44]}")

print("-" * 78)
print("all guards fired" if not fails else f"{fails} guard(s) did NOT fire")
sys.exit(1 if fails else 0)