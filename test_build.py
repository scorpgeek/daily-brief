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


def _exp_repeats_term(d):
    d = json.loads(json.dumps(d))
    d["terms"][0]["exp"] = d["terms"][0]["term"]
    return d


def _exp_missing(d):
    d = json.loads(json.dumps(d))
    del d["terms"][1]["exp"]
    return d


def _quiz_no_opts(d):
    d = json.loads(json.dumps(d))
    del d["quiz"][0]["opts"]
    return d


def _quiz_bad_answer(d):
    d = json.loads(json.dumps(d))
    d["quiz"][0]["a"] = "z"
    return d


def _quiz_one_opt(d):
    d = json.loads(json.dumps(d))
    d["quiz"][0]["opts"] = d["quiz"][0]["opts"][:1]
    return d


def _wrong_paper(d):
    d = json.loads(json.dumps(d))
    d["meta"]["newspaper"] = "The Hindu"
    return d


CASES = [
    ("missing date", None, "does-not-exist"),
    ("no top section", lambda d: {k: v for k, v in d.items() if k != "top"}, "no-top"),
    ("WATCH without watchFor", _strip_watchfor, "no-watchfor"),
    ("bad tag", _bad_tag, "bad-tag"),
    ("exp repeats term", _exp_repeats_term, "exp-echo"),
    ("exp field missing", _exp_missing, "exp-gone"),
    ("quiz without opts", _quiz_no_opts, "quiz-no-opts"),
    ("quiz answer not an option", _quiz_bad_answer, "quiz-bad-key"),
    ("quiz with one option", _quiz_one_opt, "quiz-one-opt"),
    # The base brief is valid and its newspaper is "ET Delhi", so this one
    # only fails because the filename and the brief disagree. Without the
    # guard it would publish happily and land under an unfindable name.
    ("filename beats newspaper", _wrong_paper, "et-2026-10-19"),
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


# --- two papers on one date -------------------------------------------------
# The failure this guards against is silent: both editions want the same
# filename, the second write wins, and the archive is simply missing a
# newspaper. It has to be checked by building both and looking at the disk.

def _collision():
    """Build the same date twice, once per paper, and report what landed."""
    tmp = tempfile.mkdtemp()
    made = []
    for stem, paper in (("et-2026-10-19", "ET Delhi"),
                        ("hindu-2026-10-19", "The Hindu")):
        d = json.loads(json.dumps(base))
        d["meta"]["newspaper"] = paper
        p = os.path.join(tmp, stem + ".json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)
        r = subprocess.run([sys.executable, BUILD, p, "--desk"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return False, f"{stem} failed: {(r.stdout + r.stderr).strip()[:60]}"

    arch = os.path.join(HERE, "archive")
    # Archived editions land in archive/; the stable aliases are copies at
    # the repo root, which is what the launcher links to.
    want = [os.path.join(arch, "et-2026-10-19-desk.html"),
            os.path.join(arch, "hindu-2026-10-19-desk.html"),
            os.path.join(HERE, "et-desk.html"),
            os.path.join(HERE, "hindu-desk.html")]
    missing = [os.path.basename(f) for f in want if not os.path.exists(f)]
    if missing:
        return False, f"missing {', '.join(missing)}"

    with open(os.path.join(arch, "manifest.json"), encoding="utf-8") as fh:
        rows = json.load(fh)
    that_day = [r for r in rows if r.get("date") == "2026-10-19"
                and r.get("slug") in ("et", "hindu")]
    if len(that_day) != 2:
        return False, f"manifest lists {len(that_day)} editions for 2026-10-19"

    made = ["et-desk.html", "hindu-desk.html"]
    for f in [os.path.join(arch, x) for x in
              ("hindu-2026-10-19-desk.html",)] + made:
        if os.path.exists(f):
            os.unlink(f)
    # put the real archive index back the way it was
    subprocess.run([sys.executable, BUILD,
                    os.path.join(HERE, "_raw", "2026-10-19.json"), "--desk"],
                   capture_output=True, text=True)
    return True, "et + hindu both published on 2026-10-19"


print()
ok, msg = _collision()
if not ok:
    fails += 1
print(f"{'two papers, one date':<26} {'ok' if ok else 'FAIL':<5} {msg}")

print("-" * 78)
sys.exit(1 if fails else 0)