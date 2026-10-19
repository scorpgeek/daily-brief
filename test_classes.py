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

import re
import sys

PAIRS = [("2026-10-19.html", "_tpl/phone.html"),
         ("2026-10-19-desk.html", "_tpl/desk.html")]

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


def main():
    fail = False
    for built, tpl in PAIRS:
        css_problems = check_css(tpl)

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
        print(f"  {built}: {len(used)} classes in use, "
              f"{len(unstyled)} with no CSS rule")
        for u in unstyled:
            print(f"    unstyled: .{u}")
        if css_problems or unstyled:
            fail = True

    print("css parses and every used class is styled"
          if not fail else "problems found")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())