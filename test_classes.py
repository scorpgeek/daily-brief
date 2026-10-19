"""Every class the page uses must have a rule in its template's CSS.

Catches a renderer typo where a class is emitted that nothing styles, so
the element silently renders as unstyled markup. It cannot catch a
collision with an existing rule -- the quiz's option label shipped as
`.t` and picked up the glossary tooltip styling, and `.t` was styled, so
this check was green throughout. That one was fixed at the root by
renaming `.t` to `.term`, because a one-character class name collides
with anything and no lint can guess what is safe.
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

fail = False
for built, tpl in PAIRS:
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
    print(f"{built}: {len(used)} classes in use, {len(unstyled)} with no CSS rule")
    for u in unstyled:
        print(f"    unstyled: .{u}")
    if unstyled:
        fail = True

print("every used class is styled" if not fail else "unstyled classes present")
sys.exit(1 if fail else 0)