"""Prove test_position.py fires on the exact bug it was written for.

A lint that never fails reads as coverage and is not. These are the two
shapes: the broken one that shipped, and the fixed one.
"""

import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tp", os.path.join(HERE, "test_position.py"))
tp = importlib.util.module_from_spec(spec)
sys.modules["tp"] = tp
spec.loader.exec_module(tp)

STYLE = """<style>
.app{display:grid}
.top{position:sticky;top:0}
.prog{position:absolute;left:0;right:0}
#bar{height:2px}
.tip{position:fixed}
</style>"""

CASES = [
    ("the bug that shipped: .prog is a sibling of .top",
     '<body><div class="app"><div class="top">bar</div>'
     '<div class="prog"><div id="bar"></div></div></div></body>', True),
    ("the fix: .prog is inside .top",
     '<body><div class="app"><div class="top">bar'
     '<div class="prog"><div id="bar"></div></div></div></div></body>', False),
    ("position:fixed needs no ancestor",
     '<body><div class="app"><div class="tip"></div></div></body>', False),
    ("anchored through two levels",
     '<body><div class="app"><div class="wrap"><div class="top">'
     '<div class="prog"></div></div></div></div></body>', False),
]

fail = 0
for name, body, want_problem in CASES:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("<html><head>" + STYLE + "</head>" + body + "</html>")
        built = fh.name
    tpl = built
    try:
        probs = tp.check(built, tpl)
    finally:
        os.unlink(built)
    ok = bool(probs) == want_problem
    fail += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {name}")
    for p in probs:
        print(f"       {p}")

print(f"\n{'detector agrees on every case' if not fail else str(fail) + ' mismatch(es)'}")
sys.exit(1 if fail else 0)