"""
Render both HTML editions from a brief.json.

    python build_brief.py 2026-10-19          # from _raw/2026-10-19.json
    python build_brief.py 2026-10-19.json     # explicit
    python build_brief.py 2026-10-19 --desk   # desk only

Reads   _raw/YYYY-MM-DD.json
Writes  YYYY-MM-DD.html        phone  (three bands, collapsible)
        YYYY-MM-DD-desk.html   laptop (glossary tooltips, drawer, search)

Templating is marker-based: each template holds `<!--SECTIONS-->`
(replaced with rendered body) and `/*GLOSSARY*/` (replaced with the
glossary JS object). Everything else in the template is left alone, so
the CSS and JS stay hand-editable.

Each section function returns (num, title, flag, body) or None when the
brief has nothing for it. The two wrappers turn that into phone
<details> folds or desk <h2> headings, so the content is written once.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_raw")
TPL = os.path.join(HERE, "_tpl")

TAGS = {"ACT", "WATCH", "KNOW"}


# ---------------------------------------------------------------- utils

def e(s) -> str:
    """Escape for HTML. Glossary text is authored, not scraped, but
    apostrophes are common in this content and unescaped ones break
    attribute values."""
    return html.escape(str(s), quote=True)


def esc_markup(s: str) -> str:
    """Escape, then restore the small set of inline tags this content uses."""
    s = e(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", s)
    return s


def termify(text: str, terms: dict) -> str:
    """Wrap whole-word glossary matches in <span class="t">.
    Skips anything inside a tag, so existing markup survives.
    Applied only in the desk edition, where the tooltips live."""
    if not terms:
        return text
    keys = sorted(terms, key=len, reverse=True)
    pattern = r"(?<![\w>])(" + "|".join(re.escape(k) for k in keys) + r")(?![\w<])"
    out, pos = [], 0
    for m in re.finditer(pattern, text):
        s, en = m.span()
        head = text[pos:s]
        if head.count("<") > head.count(">"):
            continue
        out.append(head)
        out.append(f'<span class="t" data-term="{e(m.group(1))}">{e(m.group(1))}</span>')
        pos = en
    out.append(text[pos:])
    return "".join(out)


# ---------------------------------------------------------------- sections
# Each returns (num, title, flag, body) or None.

def sec_thirty(b, terms):
    """Not a section — a plain block above the first band."""
    d = b.get("meta", {}).get("thirty") or {}
    if not d:
        return None
    rows = "".join(
        f"<dt>{e(k.capitalize())}</dt><dd>{termify(esc_markup(v), terms)}</dd>"
        for k, v in d.items()
    )
    return ("", "", "", f'<section class="ts"><h2>30 seconds</h2>'
                        f'<dl class="ts-row">{rows}</dl></section>')


def sec_top(b, terms):
    counts = {"ACT": 0, "WATCH": 0, "KNOW": 0}
    items = []
    for it in b.get("top", []):
        tag = str(it["tag"]).upper()
        if tag not in TAGS:
            raise ValueError(f"bad tag {it['tag']!r} — use ACT, WATCH or KNOW")
        counts[tag] += 1
        if tag == "WATCH" and not it.get("watchFor"):
            raise ValueError("WATCH item without watchFor will not serialise")
        note = ""
        if it.get("watchFor"):
            note = (f'<div class="top-note"><b>Watch for</b> '
                    f'{termify(esc_markup(it["watchFor"]), terms)}</div>')
        items.append(
            f'<div class="top-item"><span class="tag {tag}">{tag}</span>'
            f'<div class="top-text">{termify(esc_markup(it["text"]), terms)}</div>'
            f'{note}</div>'
        )
    if not items:
        return None
    flag = " · ".join(f"{k} {v}" for k, v in counts.items() if v)
    return ("01", "Top 5", flag, "\n".join(items))


def sec_lens(b, terms):
    items = []
    for l in b.get("lens", []):
        items.append(
            '<div class="lens"><dl>'
            f'<dt>What</dt><dd data-src="paper">{termify(esc_markup(l["what"]), terms)}</dd>'
            f'<dt>Why me</dt><dd>{esc_markup(l["why"])}</dd>'
            f'<dt>Do / Say</dt><dd>{termify(esc_markup(l["do"]), terms)}</dd>'
            "</dl></div>"
        )
    if not items:
        return None
    return ("06", "My Lens", None, "\n".join(items))


def sec_huddle(b, terms):
    line = termify(esc_markup(b.get("huddle", "")), terms)
    if not line:
        return None
    return ("08", "Shift Huddle Line", "Copy",
            f"<blockquote><p>{line}</p></blockquote>")


def sec_cats(b, terms):
    out = []
    for c in b.get("cats", []):
        out.append(f'<div class="h3">{esc_markup(c["name"])}</div><ul>')
        for it in c["items"]:
            out.append(f"<li>{termify(esc_markup(it), terms)}</li>")
        out.append("</ul>")
    tbl = _table_body(b)
    if tbl:
        out.append(tbl)
    if len(out) <= (1 if tbl else 0):
        return None
    return ("02", "Categories", None, "\n".join(out))


def _table_body(b):
    t = b.get("table")
    if not t:
        return ""
    cols = "".join(
        f'<th class="n">{esc_markup(h)}</th>' if i else f"<th>{esc_markup(h)}</th>"
        for i, h in enumerate(t["columns"])
    )
    rows = []
    for r in t["rows"]:
        cells = "".join(
            f'<td class="n">{esc_markup(v)}</td>' if i else f"<td>{esc_markup(v)}</td>"
            for i, v in enumerate(r)
        )
        rows.append(f"<tr>{cells}</tr>")
    return (f'<div class="tw"><table><caption>{esc_markup(t["caption"])}</caption>'
            f"<thead><tr>{cols}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>")


def sec_nums(b, terms):
    rows = "".join(
        f'<div class="num"><span class="num-v">{esc_markup(n["value"])}</span>'
        f'<span class="num-l">{esc_markup(n["label"])}</span></div>'
        for n in b.get("nums", [])
    )
    if not rows:
        return None
    return ("03", "Numbers That Matter", None, f'<div class="nums">{rows}</div>')


def sec_dates(b, terms):
    rows = "".join(
        f'<li><span class="d{" soon" if d.get("thisWeek") else ""}">'
        f'{esc_markup(d["date"])}</span>'
        f'<span class="w">{esc_markup(d["label"])}</span></li>'
        for d in b.get("dates", [])
    )
    if not rows:
        return None
    return ("04", "Dates to Watch", None, f'<ul class="dates">{rows}</ul>')


def sec_client(b, terms):
    txt = b.get("client", "")
    body = (f"<p>{termify(esc_markup(txt), terms)}</p>" if txt
            else "<p>Nothing today.</p>")
    return ("05", "Client &amp; Industry Watch", None, body)


def sec_verify(b, terms):
    items = [f"<li>{termify(esc_markup(x), terms)}</li>" for x in b.get("verify", [])]
    if not items:
        return None
    return ("07", "Verify", None, f"<ul>{''.join(items)}</ul>")


def sec_context(b, terms):
    blocks = b.get("context", [])
    if not blocks:
        return None
    out = []
    for c in blocks:
        srcs = "".join(
            (f'<li><a href="{e(s["u"])}" target="_blank" rel="noopener">'
             f'{esc_markup(s["n"])}</a> — {esc_markup(s["d"])}</li>')
            if s.get("u") else
            (f'<li>{esc_markup(s["n"])} — {esc_markup(s["d"])}</li>')
            for s in c.get("sources", [])
        )
        body = "".join(f"<p>{termify(esc_markup(p), terms)}</p>" for p in c["paras"])
        out.append(
            f'<div class="ctx" data-src="web"><div class="ctx-k">{esc_markup(c["title"])}</div>'
            f'{body}<ul class="src-list">{srcs}</ul></div>'
        )
    return ("＋", "Context — web-sourced", None, "\n".join(out))


def sec_opinion(b, terms):
    items = []
    for o in b.get("opinion", []):
        items.append(
            f'<div class="op"><h4>{termify(esc_markup(o["title"]), terms)}</h4>'
            f'<p class="op-by">{esc_markup(o.get("by", ""))}</p>'
            '<dl class="op-row">'
            f'<dt>Claim</dt><dd>{esc_markup(o["claim"])}</dd>'
            f'<dt>Support</dt><dd>{esc_markup(o["support"])}</dd>'
            f'<dt>Leaves out</dt><dd>{esc_markup(o["omits"])}</dd>'
            f'<dt>Sit with</dt><dd>{esc_markup(o["question"])}</dd>'
            f'<dt>Steal</dt><dd>{esc_markup(o["technique"])}</dd>'
            "</dl></div>"
        )
    if not items:
        return None
    return ("09", "Opinion: 2-Minute Read", None, "\n".join(items))


def sec_longform(b, terms):
    lf = b.get("longform")
    if not lf:
        return None
    o = lf["objection"]
    head = (f'<div class="op" style="border:0;padding:0 0 14px">'
            f'<h4>{termify(esc_markup(lf["title"]), terms)}</h4>'
            f'<p class="op-by">{esc_markup(lf.get("by", ""))}</p></div>')
    beats = [("The argument", lf["summary"]),
             ("The claim I'm attacking", o["claim"]),
             ("The joint", o["joint"]),
             ("The argument", o["argument"]),
             ("What I would concede", o["concede"])]
    out = [head]
    for k, v in beats:
        out.append(f'<div class="beat"><div class="beat-k">{e(k)}</div>'
                   f'<p>{termify(esc_markup(v), terms)}</p></div>')
    out.append('<div class="beat falsifier"><div class="beat-k">'
               'What would change my mind</div>'
               f'<p>{termify(esc_markup(o["falsifier"]), terms)}</p></div>')
    out.append('<div class="beat"><div class="beat-k">How this differs</div>'
               f'<p>{termify(esc_markup(o["differs"]), terms)}</p></div>')
    return ("10", "One Long-Form Read", "Objection",
            f'<div class="longform">{"".join(out)}</div>')


def sec_deep(b, terms):
    d = b.get("deep")
    if not d:
        return None
    out = []
    for s in d:
        rows = "".join(
            f'<dt>{e(k.capitalize())}</dt><dd>{termify(esc_markup(v), terms)}</dd>'
            for k, v in s["beats"].items()
        )
        out.append(
            f'<div class="dd"><h4>{termify(esc_markup(s["title"]), terms)}</h4>'
            f'<p class="dd-page">{esc_markup(s.get("page", ""))}</p>'
            f'<dl class="dd-row">{rows}</dl></div>'
        )
    return ("DEEP", "Deep Dive", f'{len(d)} stories', "\n".join(out))


def sec_words(b, terms):
    rows = "".join(
        f'<tr><td>{esc_markup(w["term"])}<span class="pos">'
        f'{esc_markup(w.get("pos", ""))}</span></td>'
        f'<td>{esc_markup(w.get("level", ""))}</td>'
        f'<td>{esc_markup(w["meaning"])}</td>'
        f'<td>{esc_markup(w.get("mine", ""))}</td></tr>'
        for w in b.get("words", [])
    )
    if not rows:
        return None
    return ("11", "Words to Learn", None,
            '<div class="tw"><table class="vocab"><thead><tr><th>Word</th><th>Lvl</th>'
            f"<th>Meaning</th><th>My example</th></tr></thead><tbody>{rows}</tbody></table></div>")


def sec_terms(b, terms):
    ts = b.get("terms", [])
    if not ts:
        return None
    # The desk template's own script fills #gbody and the rail's #glist from
    # the glossary object, so ship the empty shell and let it render. Building
    # the rows here as well would double every term.
    return ("11b", "Terms &amp; Acronyms", None,
            '<table class="gtable"><thead><tr><th>Term</th><th>What it is</th>'
            '<th>Source</th></tr></thead><tbody id="gbody"></tbody></table>')


def sec_hindi(b, terms):
    rows = "".join(
        f'<tr><td>{esc_markup(h["term"])}</td><td class="dev">{esc_markup(h["script"])}</td>'
        f'<td class="pron">{esc_markup(h["pron"])}</td></tr>'
        for h in b.get("hindi", [])
    )
    if not rows:
        return None
    return ("12", "Hindi", None,
            f'<table class="hindi"><tbody>{rows}</tbody></table>')


def sec_phrases(b, terms):
    out = "".join(
        '<div class="phrase">'
        f'<div class="phrase-t"><span class="phrase-w">{esc_markup(p["phrase"])}</span>'
        f'<span class="phrase-tone">{esc_markup(p.get("tone", ""))}</span></div>'
        f'<p class="phrase-m">{esc_markup(p["meaning"])}</p>'
        f'<p class="phrase-e">{esc_markup(p["example"])}</p></div>'
        for p in b.get("phrases", [])
    )
    if not out:
        return None
    return ("13", "Phrases for Daily Life", None, out)


def sec_traps(b, terms):
    out = "".join(
        '<div class="trap"><div class="trap-row">'
        f'<span class="trap-bad">{esc_markup(t["bad"])}</span>'
        f'<span class="trap-good"><b>→</b> {esc_markup(t["good"])}</span>'
        f'<div class="trap-why">{esc_markup(t["why"])}</div></div></div>'
        for t in b.get("traps", [])
    )
    if not out:
        return None
    return ("14", "Traps in My English", None, out)


def sec_speak(b, terms):
    s = b.get("speak")
    if not s:
        return None
    model = esc_markup(s["model"]).replace("\n\n", "<br><br>").replace("\n", "<br>")
    return ("15", "Speak", None,
            '<div class="speak"><h4>Prompt</h4>'
            f'<p class="q">{esc_markup(s["prompt"])}</p>'
            "<h4>Model answer</h4>"
            f'<div class="model">{model}</div></div>')


def sec_quiz(b, terms):
    q = b.get("quiz", [])
    if not q:
        return None
    items = "".join(
        f'<div class="qa"><p class="q"><b>{i}.</b> {esc_markup(x["q"])}</p></div>'
        for i, x in enumerate(q, 1)
    )
    ans = "".join(
        f'<div class="qa"><p class="a"><b>{e(x["a"])}</b> — {esc_markup(x["why"])}</p></div>'
        for x in q
    )
    return ("16", "Quiz", None,
            f'{items}<div class="ans-head">Answers</div>{ans}')


def sec_skip(b, terms):
    txt = b.get("skip", "")
    if not txt:
        return None
    return ("17", "Skip List", None, f'<div class="skip">{esc_markup(txt)}</div>')


SECTIONS = {
    "thirty": sec_thirty, "top": sec_top, "lens": sec_lens, "huddle": sec_huddle,
    "cats": sec_cats, "nums": sec_nums, "dates": sec_dates, "client": sec_client,
    "verify": sec_verify, "context": sec_context, "opinion": sec_opinion,
    "longform": sec_longform, "deep": sec_deep, "words": sec_words,
    "terms": sec_terms, "hindi": sec_hindi, "phrases": sec_phrases,
    "traps": sec_traps, "speak": sec_speak, "quiz": sec_quiz, "skip": sec_skip,
}

DESK_ORDER = ["thirty", "top", "lens", "huddle", "deep", "longform",
              "cats", "nums", "dates", "client", "verify", "context",
              "opinion", "words", "terms", "hindi", "phrases",
              "traps", "speak", "quiz", "skip"]

# (class, label, note, keys, open by default?)
PHONE_BANDS = [
    ("band-use", "Use these",
     "Three quick sections, then the two deep reads. Everything below is reference.",
     ["top", "lens", "huddle", "deep", "longform"], True),
    ("band-ref", "Reference", "Scan, don't read. Each section is folded by default.",
     ["cats", "nums", "dates", "client", "verify", "opinion"], False),
    ("band-lang", "Language", "Words, corrections, and the practice set.",
     ["words", "hindi", "phrases", "traps", "speak", "quiz", "skip"], False),
]


# ---------------------------------------------------------------- assembly

def render_sections(b, terms, key):
    """Run one section function, returning (num, title, flag, body) or None."""
    return SECTIONS[key](b, terms)


def build_desk(b, terms) -> str:
    out = []
    for key in DESK_ORDER:
        got = render_sections(b, terms, key)
        if not got:
            continue
        num, title, flag, body = got
        if key == "thirty":
            out.append(body)          # plain block, no section heading
            continue
        flag_html = f'<span class="sec-flag">{e(flag)}</span>' if flag else ""
        out.append(f'<section id="{key}">\n'
                   f'<h2 class="sec"><span class="n">{e(num)}</span>{title}'
                   f"{flag_html}</h2>\n{body}\n</section>")
    return "\n\n".join(out)


def build_phone(b, terms) -> str:
    # The phone edition has no tooltip layer, so no term spans. Passing an
    # empty glossary makes every section fall back to plain escaped text.
    terms: dict = {}
    out = []
    thirty = render_sections(b, terms, "thirty")
    if thirty:
        out.append(thirty[3])         # 30 seconds sits above the first band

    for cls, label, note, keys, is_open in PHONE_BANDS:
        folds = []
        for key in keys:
            got = render_sections(b, terms, key)
            if not got:
                continue
            num, title, flag, body = got
            flag_html = f'<span class="sec-flag">{e(flag)}</span>' if flag else ""
            folds.append(
                f'<details class="sec"{" open" if is_open else ""}>'
                f'<summary><span class="chev"></span><span class="sec-n">{e(num)}</span>'
                f'<span class="sec-title">{title}</span>{flag_html}</summary>'
                f'<div class="sec-body">{body}</div></details>'
            )
        if not folds:
            continue
        out.append(
            f'<div class="band {cls}">\n'
            f'<div class="band-head"><span class="band-label">{label}</span>'
            f'<span class="band-rule"></span></div>\n'
            f'<p class="band-note">{e(note)}</p>\n'
            f'{"".join(folds)}\n</div>'
        )
    return "\n\n".join(out)


def glossary_js(terms) -> str:
    payload = []
    for t in terms:
        payload.append(
            # G is keyed by term; each value repeats the term in .t so the drawer can
# label an abbreviation and its expansion separately.
        '{k}: {{t:{k},exp:{e},def:{d},full:{f},paper:{p},page:{g},srcs:{s}}}'.format(
                k=json.dumps(t["term"]),
                e=json.dumps(t.get("exp") or ""),
                d=json.dumps(t["def"]),
                f=json.dumps(t.get("full", "")),
                p=json.dumps(t.get("paper", "")),
                g=json.dumps(t.get("page", "")),
                s=json.dumps(t.get("sources", []), ensure_ascii=False),
            )
        )
    return "{" + ",\n ".join(payload) + "}"


def lint_terms(b: dict) -> None:
    """Every term must say whether it is an abbreviation, and say so honestly.

    The rail prints the full form under the term; the drawer labels it
    'abbreviation' or 'term'. Copying the term into `exp` to mean 'no
    expansion' is the failure mode that shipped six entries reading
    'NIM NIM' and one labelled a term when it is an abbreviation. Use an
    empty string instead.
    """
    bad = []
    for t in b.get("terms", []):
        name = t.get("term", "?")
        if "exp" not in t:
            bad.append(f"{name}: no exp field — use \"\" if it is not an abbreviation")
        elif t["exp"] == t.get("term"):
            bad.append(f'{name}: exp repeats the term — use "" or the real full form')
    if bad:
        sys.exit("glossary: " + "; ".join(bad))


def render(tpl_name: str, b: dict, out_path: str, mode: str) -> None:
    with open(os.path.join(TPL, tpl_name), encoding="utf-8") as fh:
        tpl = fh.read()

    terms = {t["term"]: t for t in b.get("terms", [])}
    body = build_phone(b, terms) if mode == "phone" else build_desk(b, terms)
    meta = b.get("meta", {})

    subs = {
        "<!--SECTIONS-->": body,
        "/*GLOSSARY*/": glossary_js(b.get("terms", [])),
        "{{DATE_LONG}}": meta.get("dateLong", meta.get("date", "")),
        "{{NEWSPAPER}}": meta.get("newspaper", ""),
        "{{PAGES}}": str(meta.get("pages", "")),
        "{{MODE}}": meta.get("mode", ""),
        "{{UNREADABLE}}": " · ".join(meta.get("unreadable", [])) or "none",
        "{{ENRICHED}}": meta.get("enriched", ""),
    }
    for k, v in subs.items():
        tpl = tpl.replace(k, v)

    leftover = [k for k in subs if k in tpl]
    if leftover:
        sys.exit(f"{tpl_name}: markers still present after render: {leftover}")

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(tpl)
    print(f"  wrote {os.path.basename(out_path)}  ({len(tpl)//1024} KB)")
    check_scripts(out_path)


SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S | re.I)


def check_scripts(path: str) -> None:
    """Syntax-check every inline <script> in the rendered file.

    Substituted content lands inside script blocks (the glossary object),
    so a bad substitution can produce a file that looks fine but throws
    on load and silently kills the whole interactive layer. `node --check`
    catches it at build time instead.
    """
    if not shutil.which("node"):
        return
    with open(path, encoding="utf-8") as fh:
        blocks = SCRIPT_RE.findall(fh.read())
    for i, js in enumerate(blocks, 1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8") as tmp:
            tmp.write(js)
            tmp_js = tmp.name
        try:
            r = subprocess.run(["node", "--check", tmp_js],
                               capture_output=True, text=True)
            if r.returncode != 0:
                name = os.path.basename(path)
                sys.exit(f"{name}: inline script block {i} does not parse\n"
                         + r.stderr.strip())
        finally:
            os.unlink(tmp_js)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    desk_only = "--desk" in sys.argv
    stem = os.path.splitext(os.path.basename(args[0]))[0] if args else ""
    src = args[0] if (args and args[0].endswith(".json")) else os.path.join(RAW, stem + ".json")

    if not stem or not os.path.exists(src):
        sys.exit(f"usage: build_brief.py YYYY-MM-DD[.json] [--desk]\nnot found: {src}")
    if not os.path.isdir(TPL):
        sys.exit(f"template dir missing: {TPL}")

    with open(src, encoding="utf-8") as fh:
        b = json.load(fh)

    missing = [k for k in ("meta", "top") if k not in b]
    if missing:
        sys.exit(f"brief is missing required field(s): {', '.join(missing)}")

    print(f"building {stem}")
    try:
        lint_terms(b)
        if not desk_only:
            render("phone.html", b, os.path.join(HERE, stem + ".html"), "phone")
        render("desk.html", b, os.path.join(HERE, stem + "-desk.html"), "desk")
    except (ValueError, KeyError) as exc:
        # A hand-written brief should fail with a sentence, not a traceback.
        sys.exit(f"{stem}.json: {exc}")


if __name__ == "__main__":
    main()