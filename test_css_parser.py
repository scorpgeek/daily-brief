"""Prove the CSS checks in test_classes.py actually fire.

A lint that never fails is worse than no lint: it reads as coverage and
is not. These are the two shapes that shipped — a missing closing brace
and a selector nested inside a declaration list.
"""

import importlib.util
import io
import os
import sys
import tempfile

spec = importlib.util.spec_from_file_location(
    "tc", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "test_classes.py"))
tc = importlib.util.module_from_spec(spec)
sys.modules["tc"] = tc
spec.loader.exec_module(tc)

CASES = [
    # name, css, expect_clean
    ("missing closing brace",
     ".a{color:red}\n@media(x){.b{display:none}", False),
    ("extra closing brace",
     ".a{color:red}}\n.b{display:none}", False),
    ("selector nested in declarations",
     "@media(prefers-reduced-motion:reduce){*{transition:none!important;html{scroll-behavior:auto}}", False),
    ("the real phone bug",
     "@media (prefers-reduced-motion:reduce){\n  *{transition:none!important;html{scroll-behavior:auto}}\n}", False),
    ("the real desk bug",
     "@media(prefers-reduced-motion:reduce){*{transition:none!important;html{scroll-behavior:auto}}\n.totop{opacity:0}", False),
    ("balanced rule",
     ".a{color:red}.b{display:none}", True),
    ("balanced media",
     "@media (prefers-reduced-motion:reduce){\n  *{transition:none!important}\n  html{scroll-behavior:auto}\n}", True),
    ("nested media is legal",
     "@media(max-width:900px){:root{--rail:0px}.rail{display:none}}", True),
]

fail = 0
for name, css, want_clean in CASES:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False,
                                     encoding="utf-8") as fh:
        fh.write("<style>" + css + "</style>")
        path = fh.name
    try:
        problems = tc.check_css(path)
    finally:
        os.unlink(path)
    clean = not problems
    ok = clean == want_clean
    fail += 0 if ok else 1
    print(f"{'ok  ' if ok else 'FAIL'} {name:<34} {problems or 'clean'}")

print(f"\n{'detector agrees on every case' if not fail else str(fail) + ' mismatch(es)'}")
sys.exit(1 if fail else 0)