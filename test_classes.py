"""Check every class the page uses has a rule in its template's CSS,
and that the CSS itself parses.

Catches a renderer typo where a class is emitted that nothing styles, so
the element silently renders as unstyled markup. It cannot catch a
collision with an existing rule -- the quiz's option label shipped as
`.t` and picked up the glossary tooltip styling, and `.t` was styled, so
this check was green throughout. That one was fixed at the root by
renaming `.t` to `.term`, because a one-character class name collides
with anything and no lint can guess what is safe.

The brace walk is here because node --check only parses JS. A missing
closing brace once nested the whole back-to-top block inside
@media(prefers-reduced-motion:reduce), so it applied only when the reader
had reduced motion switched on. Valid-looking file, zero rules applied.
"""

import glob
import os
import re
import sys


def newest(pattern):
    """Latest match by filename, so the checks follow the archive rather
    than a hardcoded date that goes stale the next build."""
    hits = sorted(glob.glob(pattern))
    return hits[-1] if hits else None


def pairs():
    """(built, template) for the current edition plus the newest archived
    one. The aliases always exist; the archive entry means a template
    change that breaks an older edition is caught too."""
    out = []
    p, d = newest("archive/*[0-9].html"), newest("archive/*-desk.html")
    if p:
        out.append((p, "_tpl/phone.html"))
    if d:
        out.append((d, "_tpl/desk.html"))
    out += [("phone.html", "_tpl/phone.html"), ("desk.html", "_tpl/desk.html")]
    return [(a, b) for a, b in out if a and os.path.exists(a)]

# Markup shared by both editions, styled differently by each. On the phone
# these have their own rules; on the desk they are picked up from a parent.
#   .top-text — a grid cell of .top-item, which supplies the columns
#   .ts-row    — matched by .ts dl, which supplies the label/value grid
# Neither is unstyled output; both are deliberate.
INHERITED = {"top-text", "ts-row"}


def check_css(path):
    src = open(path, encoding="utf-8").read()
    css = src[src.index("<style>"):src.index("</style>")]

    depth = 0
    seen_decl = False
    line = 1
    problems = []
    for ch in css:
        if ch == "\n":
            line += 1
        elif ch == ";":
            seen_decl = True
        elif ch == "{":
            if depth and seen_decl:
                problems.append((line, "selector nested inside a declaration list"))
            seen_decl = False
            depth += 1
        elif ch == "}":
            depth -= 1
            seen_decl = False
            if depth < 0:
                problems.append((line, "unbalanced }"))
                depth = 0
    if depth:
        problems.append((line, f"{depth} unclosed {{ at end of stylesheet"))
    return problems


def check_elements(path):
    """Every element the inline JS reaches for must exist in the markup.

    Cutting the templates down to markers dropped <div id="res">, so
    doSearch() threw on res.innerHTML and search was dead while every
    other check stayed green. The CSS for .res was still fully present,
    which is what made it look like a styling problem rather than a
    missing node.
    """
    src = open(path, encoding="utf-8").read()
    html_only = re.sub(r"<script.*?</script>", "", src, flags=re.S)
    js = "".join(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", src, re.S))

    ids = set(re.findall(r'\bid="([^"]+)"', html_only))
    problems = []

    for wanted in sorted(set(re.findall(r"getElementById\(['\"]([^'\"]+)['\"]\)", js))):
        if wanted not in ids:
            problems.append(f"getElementById({wanted!r}) -> no such id")

    classes = set()
    for attr in re.findall(r'\bclass="([^"]+)"', html_only):
        classes.update(attr.split())
    for wanted in sorted(set(re.findall(r"querySelector(?:All)?\(['\"]\.([\w-]+)", js))):
        if wanted not in classes:
            problems.append(f"querySelector('.{wanted}') -> no element has that class")

    # Nav links ship as href="#" because the same file is served from the
    # root and from archive/, which is one level deeper. If the resolver is
    # renamed or removed they stay at "#" and silently do nothing, so check
    # the hooks are actually wired.
    for hook in sorted(set(re.findall(r"\b(data-(?:archive|today))[\s>]", html_only))):
        # match the bracketed selector, not a bare substring: "[data-archiveX]"
        # contains "data-archive" and would pass a substring test while being
        # exactly the rename this is meant to catch
        if f"[{hook}]" not in js:
            problems.append(f"{hook} anchors present but no script resolves them")

    return problems


def check_anchors(path):
    """Every in-page link must resolve to an element that exists.

    Three of the seven rail links pointed at #top5, #markets and
    #glossary; the sections are #top, #cats and #terms. The links looked
    fine and the ids looked fine — they just did not correspond, so
    clicking did nothing. Nothing else in the build looks at hrefs.
    """
    src = open(path, encoding="utf-8").read()
    body = src[src.index("<body"):]
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)

    ids = set(re.findall(r'\bid="([^"]+)"', src))
    targets = set()
    for href in re.findall(r'href="#([^"]+)"', body):
        targets.add(href)
    # links the Index dialog builds at runtime, from the same ids
    return sorted(f"href=\"#{t}\" -> no element with that id" for t in targets - ids)


def main():
    fail = False
    for built, tpl in pairs():
        css_problems = check_css(tpl)
        el_problems = check_elements(built)
        anchor_problems = check_anchors(built)

        html = open(built, encoding="utf-8").read()
        css = open(tpl, encoding="utf-8").read()
        css = css[css.index("<style>"):css.index("</style>")]

        body = html[html.index("<body"):]
        body = re.sub(r"<script.*?</script>", "", body, flags=re.S)

        used = set()
        for m in re.finditer(r'class="([^"]+)"', body):
            used.update(m.group(1).split())

        unstyled = sorted(c for c in used
                          if f".{c}" not in css and c not in INHERITED)

        print(f"{tpl}")
        print(f"  css: {'ok' if not css_problems else ''}")
        for ln, msg in css_problems:
            print(f"    line {ln}: {msg}")
        for p in el_problems + anchor_problems:
            print(f"    {p}")
        print(f"  {built}: {len(used)} classes in use, "
              f"{len(unstyled)} unstyled, "
              f"{len(el_problems)} missing JS targets, "
              f"{len(anchor_problems)} dead anchors")
        for u in unstyled:
            print(f"    unstyled: .{u}")
        if css_problems or unstyled or el_problems or anchor_problems:
            fail = True

    print("css parses, js targets resolve, anchors resolve, classes are styled"
          if not fail else "problems found")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())