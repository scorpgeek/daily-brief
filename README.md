# Daily Brief

Turns a newspaper PDF into two single-page HTML briefings — one built for a
phone, one built for a laptop — plus a categorised written briefing with a
reading-practice section.

## What it is

A personal reading pipeline:

1. **Extract** — `extract_pdf.py` pulls text out of the PDF, handling the
   subsetted fonts a magazine PDF ships with.
2. **Summarise** — a prompt spec turns the text into a structured briefing
   across 17 sections.
3. **Build** — `build_brief.py` reads a JSON brief and fills two templates,
   producing both editions.

```
extract_pdf.py   PDF -> _raw/YYYY-MM-DD.txt
                 (brief is written by hand / by the assistant)
                 _raw/YYYY-MM-DD.json
build_brief.py   _raw/YYYY-MM-DD.json -> archive/YYYY-MM-DD.html      (phone)
                                           archive/YYYY-MM-DD-desk.html (laptop)
                                           phone.html                  (stable alias)
                                           desk.html                   (stable alias)
                                           archive/manifest.json
```

The stable aliases are what `index.html` routes to. The dated editions live
in `archive/` and are gitignored, so without the aliases the published site
has nothing current to point at and falls back to whatever sample was last
committed — which is how it came to be serving a hardcoded snapshot from two
days ago.

`archive/manifest.json` is written on every build: one line per edition,
with the paper, page count, mode and lead story. `ARCHIVE.html` reads it,
because a browser cannot enumerate a directory.

The JSON is the single source of truth. Both editions render from it, so
they cannot drift, and the glossary that powers the laptop tooltips is the
same data as the Terms & Acronyms table — not a second transcription of it.

## The two editions

**Phone** — three bands so the sections you act on are not buried under the
ones you only reference. Everything folds; only the first band is open.

```
USE THESE      Top 5 · My Lens · Shift Huddle Line · Deep Dive · Long-Form Read
REFERENCE      Categories · Numbers · Dates · Client Watch · Verify · Opinion
LANGUAGE       Words · Hindi · Phrases · Traps · Speak · Quiz · Skip List
```

**Laptop** — a rail, a reading column, and a drawer that slides in when you
click a term. Adds a glossary with the paper's own sentence and dated
external sources, a provenance toggle that hides everything not from the
paper, `Cmd/Ctrl+K` search, and reading-preference controls.

Search results dismiss themselves. They used to sit there until you deleted
the letters by hand, which left a stale panel over the document after you had
already moved on. Now Escape, a click anywhere else, and any navigation all
close them — and Enter opens the first result, because typing a term and
pressing Enter is the reflex. Escape peels one layer at a time: results
first, glossary drawer second.

The rail holds the document identity — paper, date, page count, mode — and
the sticky bar shows where you are: the current section, its number, how far
through you are, and a progress hairline. They used to print the date twice
in two different formats, side by side, because both surfaces are sticky and
neither was willing to give it up.

The **Index** button opens the whole section list — all twenty-one, grouped
the way the document is grouped. The rail can only hold seven without
becoming a wall, so fourteen sections were unreachable from it.

Built from the sections actually on the page and grouped by a `data-band`
the renderer stamps on each one, so a short brief and a long one both index
correctly and nothing is listed twice. Arrow keys move, Enter jumps, Escape
or a backdrop click closes. Native `<dialog>`, so focus trapping is the
browser's problem, not ours.

Both editions carry a back-to-top button that appears once you are past the
first screen. Seventeen folds stack a long way down and neither device has a
useful Home key.

The external-sourced material is always labelled. Nothing web-sourced is
allowed into a news section; it appears only in the glossary and the
`Context` blocks, which carry their own source lists.

## Files

```
extract_pdf.py     PDF -> _raw/YYYY-MM-DD.txt
build_brief.py     _raw/YYYY-MM-DD.json -> both HTML editions
test_build.py      rejection paths for the build lints
test_classes.py    CSS parses, JS targets resolve, anchors resolve, classes styled
test_position.py   every absolutely-positioned element is anchored
test_css_parser.py proves the CSS check actually fires
test_position_parser.py proves the positioning check actually fires
_tpl/phone.html    phone template  (markers: <!--SECTIONS-->)
_tpl/desk.html     laptop template (markers: <!--SECTIONS-->, /*GLOSSARY*/)
index.html         launcher: picks an edition by viewport, remembers the choice
ARCHIVE.html       past editions, grouped by month, filterable
phone.html         published phone edition
desk.html          published laptop edition
README.md          this file
```

Templates are hand-editable. `build_brief.py` only substitutes two markers
and the header fields; the CSS and JS are yours to change.

Two things are deliberately **not** in this repo:

- `PROMPT.md` — the briefing spec. It names an employer, a client account and
  career goals, and Pages requires a public repo, so it stays local.
- `_raw/` — extracted article text and the dated JSON briefs. Copyrighted.

## Usage

Extract:

```powershell
python extract_pdf.py
python extract_pdf.py "path\to\issue.pdf"    # explicit file
python extract_pdf.py --folder "D:\News"     # custom inbox
python extract_pdf.py --out-dir "C:\raw"     # custom output
```

The inbox defaults to `~/Downloads/Telegram Desktop`. It picks the newest PDF
by modification time, so re-running on the same day just overwrites.

Build:

```powershell
python build_brief.py 2026-10-19          # both editions
python build_brief.py 2026-10-19 --desk   # laptop only
```

The build refuses to write a file with unsubstituted markers, and
syntax-checks every inline `<script>` with `node --check` — a bad glossary
substitution otherwise produces a page that looks fine and silently kills
the whole interactive layer.

It also lints the brief: a `WATCH` item with no trigger, a top tag that is
not ACT/WATCH/KNOW, a glossary `exp` that just echoes its term, a quiz
question with no options or an answer key pointing at an option that is not
there. Each of those shipped once.

```powershell
python test_build.py     # the rejection paths
python test_classes.py   # CSS parses, JS targets resolve, classes are styled
python test_position.py  # every absolutely-positioned element is anchored
```

`test_classes.py` also checks that every element the inline JS reaches for
actually exists, and that every `href="#..."` resolves to an id that is
actually there. Cutting the templates down to markers had silently dropped
`<div id="res">`, so `doSearch()` threw on `res.innerHTML` and search was
dead while every other check stayed green — the CSS for `.res` was still
fully present, which is exactly what made it look like a styling problem
rather than a missing node. Three of the seven rail links pointed at
`#top5`, `#markets` and `#glossary` when the sections are `#top`, `#cats`
and `#terms`; the links looked fine and the ids looked fine, they just did
not correspond.

`test_position.py` checks that every `position:absolute` element has a
positioned ancestor, because that ancestor is what defines its containing
block. The reading-progress bar was once emitted as a *sibling* of `.top`
rather than a child; `.app` is not positioned, so it fell through to the
initial containing block and rendered pinned to the bottom of the viewport,
full width, 2px of red — with the page sliding behind it, which read as
"the bar moves with scroll". Nothing was mis-coloured or mis-sized; it was
exactly where CSS said it should be, just not where anyone meant.

Each checker has a companion `test_*_parser.py` that runs it against the
exact shape it was written for. A lint that never fails reads as coverage
and is not.

Serve locally and open on a phone on the same network:

```powershell
python -m http.server 8899 --bind 0.0.0.0
```

Then `http://<your-ip>:8899/`.

## Archive

Every build lands in `archive/` and updates `archive/manifest.json`.
`ARCHIVE.html` lists them by month with the paper, page count and lead story,
filterable by date, paper or headline. It degrades honestly: an edition with
no record shows a dash rather than a guessed figure, and if the manifest is
missing the page says so and links to today's briefing instead of listing
editions it cannot open.

Archived editions keep whatever design they were built with. The 18 Oct file
predates the band layout and still renders in the older card format; that is
what an archive is for.

`archive/` is tracked and published. It grows by roughly 140 KB a day. If that
ever matters, prune old editions rather than untracking the folder — otherwise
the index will list days whose files are missing.

`index.html` is a launcher, not a briefing. It sends a wide screen to
`desk.html` and a narrow one to `phone.html`, remembers an explicit choice
in `localStorage` so it never fights you, and stays put with an explanation
if either file is missing rather than dumping you on a 404.

To refresh the public site after a build, commit the aliases and the archive:

```powershell
git add phone.html desk.html archive
git commit -m "Publish today's brief"
```

Only those. The extracted article text in `_raw/` stays untracked.

## Publishing

## Extraction notes

Magazine PDFs are multi-column and `pypdf` reads across columns rather than
down them. In practice this is recoverable — headlines, decks and bullet
points land next to their own body text. Two things to watch:

- **Sidebar boxes** split from their article. Reassign by content, not position.
- **Continuation articles** are marked `From Page 1`. Join them before
  summarising or the story gets attributed to the wrong headline.

Install with `pip install pypdf`.

## Design notes

- Serif headings, sans body, generous line-height. The measure is capped so
  lines don't run long on a laptop.
- Light by default, dark one click away in the top bar. There is only one
  theme control — an earlier version had a second copy in the rail and two
  controls for one setting is one too many. The choice persists.
- The light theme uses no pure white and no pure black. Halation around
  glyphs on a white field is what makes a light theme tiring after an hour,
  so the surface is a warm off-white and the text a warm near-black.
- Both themes were solved against WCAG AA rather than hand-picked. Every text
  token clears 4.5:1 on every surface it appears on, in both themes, in both
  editions. `--faint` carries every small mono label and was the one that
  failed at 2.5:1 — it now clears 4.5:1.
- Chips keep a 13% tint of their own accent, because below that they stop
  reading as chips. That tint eats the contrast the accent just won, so each
  chip has its own text token solved against the tinted background.
- The rail glossary stacks term over expansion rather than setting them side
  by side. The rail is too narrow for two columns, and a fixed-width term
  column made long terms collide with the text beside them. The expansion is
  dropped when it only repeats the term, so the list reads `NIM`, not
  `NIM NIM`.
- One 120 ms transition on the disclosure chevron, and one on the
  back-to-top button's fade. Nothing else. Motion in a late-night reading
  document is a cost, not a feature.
- Tables are capped at 4 columns and always preceded by a sentence carrying
  the headline number, so a phone reader who never scrolls still gets it.
- Part-of-speech is shown in the laptop vocab table and hidden on the phone,
  where it would break the measure.