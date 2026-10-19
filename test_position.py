"""Check that absolutely-positioned elements have a positioned ancestor.

The reading-progress bar was emitted as a sibling of .top rather than a
child. .app is not positioned, so the bar fell through to the initial
containing block and rendered pinned to the bottom of the viewport, full
width, 2px of red -- with the page sliding behind it, which read as "the
bar moves with scroll". Nothing was mis-coloured or mis-sized; it was
exactly where CSS said it should be, just not where anyone meant.

No static check catches that, so this one walks the DOM: every element
whose class resolves to position:absolute must have an ancestor-or-self
that is positioned, because that ancestor is what defines its containing
block.
"""

import re
import sys
from html.parser import HTMLParser

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}


def css_rules(css):
    """Map each simple selector in the sheet to its position value."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out = {}
    for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        m = re.search(r"(?<![\w-])position\s*:\s*([a-z-]+)", body)
        if not m:
            continue
        pos = m.group(1)
        if pos == "static":
            continue
        for part in sel.split(","):
            part = part.strip()
            if not part or part.startswith("@") or ":" in part:
                continue          # pseudo-selectors: too coarse to resolve
            for tok in re.findall(r"[.#]?[\w-]+", part):
                out[tok] = pos
    return out


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "#root", "attrs": {}, "children": [], "parent": None}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": [], "parent": self.stack[-1]}
        self.stack[-1]["children"].append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i]["tag"] == tag:
                del self.stack[i:]
                return


def tokens(node):
    t = [node["tag"].upper()]
    if node["attrs"].get("class"):
        t += ["." + c for c in node["attrs"]["class"].split()]
    if node["attrs"].get("id"):
        t += ["#" + node["attrs"]["id"]]
    return t


def check(built, tpl):
    css = open(tpl, encoding="utf-8").read()
    css = css[css.index("<style>"):css.index("</style>")]
    rules = css_rules(css)

    src = open(built, encoding="utf-8").read()
    p = Tree()
    p.feed(src)

    problems = []

    def walk(node):
        toks = tokens(node)
        own = next((rules[t] for t in toks if t in rules), None)
        if own == "absolute":
            anc = node["parent"]
            found = None
            while anc is not None:
                found = next((rules[t] for t in tokens(anc) if t in rules), None)
                if found:
                    break
                anc = anc["parent"]
            if not found:
                label = " ".join(toks[:3])
                problems.append(
                    f"{label}: position:absolute with no positioned ancestor "
                    f"-> falls back to the initial containing block")
        for c in node["children"]:
            walk(c)

    walk(p.root)
    return problems


if __name__ == "__main__":
    import os
    pairs = [("2026-10-19.html", "_tpl/phone.html"),
             ("2026-10-19-desk.html", "_tpl/desk.html")]
    fail = False
    for built, tpl in pairs:
        probs = check(built, tpl)
        print(f"{built}: {len(probs)} unanchored absolute element(s)")
        for p_ in probs:
            print(f"    {p_}")
        if probs:
            fail = True
    print("every absolute element has a positioned ancestor"
          if not fail else "problems found")
    sys.exit(1 if fail else 0)