# Daily Brief

Turns a newspaper PDF into two single-page HTML briefings — one built for a
phone, one built for a laptop — plus a categorised written briefing with a
reading-practice section.

It reads more than one paper. The Economic Times and The Hindu both work, and
each gets its own complete edition; `index.html` asks which one you want.

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
build_brief.py   _raw/YYYY-MM-DD.json -> archive/<paper>-YYYY-MM-DD.html      (phone)
                                           archive/<paper>-YYYY-MM-DD-desk.html (laptop)
                                           <paper>.html                       (stable alias)
                                           <paper>-desk.html                  (stable alias)
                                           archive/manifest.json
```

`<paper>` is a short slug derived from `meta.newspaper` — `et`, `hindu` — and it
appears in every filename. It has to: two papers on the same date would both
want `archive/2026-10-19.html`, and the second build would silently overwrite
the first, leaving the archive with a hole where a day should be.

The stable aliases are what `index.html` routes to. They are generated at build
time, so the launcher checks one exists with a `HEAD` request before sending
anyone to it; an alias that was never committed lands you on the chooser with an
explanation instead of a 404. `phone.html` and `desk.html` survive as one-line
redirects to that chooser, because they were published and bookmarked and there
is no longer a single paper they could honestly point at.

`archive/manifest.json` is written on every build: one line per edition, keyed
by paper and date, with the page count, mode and lead story. `ARCHIVE.html`
reads it, because a browser cannot enumerate a directory. Rows naming a file
that isn't on disk are dropped on write, so the index can't advertise an
edition that 404s.

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

## Read aloud

A **Listen** button sits in the top bar of both editions. It opens a panel
listing every section, grouped the way the document is grouped, and reads the
briefing aloud in the browser's own speech engine — so it costs nothing to
build, needs no key, and works on a phone with no connection.

The word being read is highlighted in the page as it goes, which is the point
for someone learning the language: you can follow the text and see the word
you are hearing. Speed is adjustable (0.8×, 1×, 1.15×) and the voice is
selectable, preferring en-GB for a Canadian account, then en-IN, then en-US.

**Which voices exist is a property of the device, not of this page.** A phone
and a laptop ship completely different sets, and the list can change when an
OS update adds a language pack. So the panel lists every voice the device
actually has, with its language code, and states how many there are — and
says plainly when the browser has no speech engine at all rather than
offering an empty dropdown. The default order is a judgement, not a fact:
en-GB first for a Canadian account, then en-IN for the night shift, then
en-US, then everything else alphabetically.

**Closing the panel stops the reading.** That lives on the dialog's `close`
event rather than on the close button, because Escape fires `close` without
touching the button — and a panel dismissed with the keyboard used to keep
talking with nothing on screen to stop it. The backdrop click closes too, the
way the Index does, and `pagehide` stops the speech when the page is left
for good. Backgrounding the tab does not fire `pagehide`, so the reading
carries on while you do something else.

Two decisions worth recording:

**The text is read in blocks, not as one utterance.** Chrome silently truncates
an utterance at about fifteen seconds, and a single utterance gives nowhere to
show how far the reading has got. Blocks — paragraphs, list items, tables —
also make the highlighting possible, because the offsets the engine reports
line up with the text nodes of one block. A keep-alive timer pauses and
resumes every nine seconds, which is the long-standing workaround for the
same Chrome bug on the occasional block that still runs long.

A `<dt>` is read together with the `<dd>` that follows it, as one chunk. The
"30 seconds" block and My Lens are both definition lists, and reading the
label on its own — "What", "Today" — before the sentence it belongs to is a
stutter. As one chunk it reads "What. Delhi pandal organisers say an earlier
forced closing time is making crowd control worse."

**Changing the speed or the voice restarts the current audio.** The rate and
the voice are fixed when an utterance is created, so changing either one
mid-sentence otherwise does nothing to the sound you are hearing — it only
affects the next block. The reading is therefore cancelled and re-spoken
from the word you are on, not from the start of the paragraph, so the change
is heard immediately without repeating what you have just heard. Every
utterance carries a generation number, so the cancelled one is recognised
and ignored rather than advancing the queue behind the new audio.

**The list is built from a `<template>`, not from an HTML string.** The
template row is in the markup, so the class the script reaches for is
visible in the source and to the checker that verifies every class the
inline JS touches actually exists. Building the list from a string would
have made that check a permanent false alarm.

The phone edition gets a bottom sheet rather than a centred panel, because
that edition is read one-handed, often at night. `display:flex` is set only
on `[open]` — setting it on the dialog at all would defeat the user-agent
rule that keeps a closed dialog hidden.

## Files

```
extract_pdf.py     PDF -> _raw/YYYY-MM-DD.txt
build_brief.py     _raw/YYYY-MM-DD.json -> both HTML editions
test_build.py      rejection paths for the build lints
test_classes.py    CSS parses, JS targets resolve, anchors resolve, classes styled
test_position.py   every absolutely-positioned element is anchored
test_css_parser.py proves the CSS check actually fires
test_position_parser.py proves the positioning check actually fires
_tpl/phone.html    phone template  (markers: <!--SECTIONS-->, <!--TTS-->)
_tpl/desk.html     laptop template (markers: <!--SECTIONS-->, /*GLOSSARY*/, <!--TTS-->)
_tpl/tts.js        the read-aloud module, inlined into both templates
index.html         launcher: picks a newspaper, then an edition by viewport
ARCHIVE.html       past editions, grouped by newspaper then month, filterable
<paper>.html       published phone edition, one per newspaper
<paper>-desk.html  published laptop edition, one per newspaper
phone.html / desk.html   old paths, now redirects to the launcher
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

## The daily loop, by hand

Four of the five steps are already single commands. The fifth is the
briefing itself, which is written by hand — deliberately, so nothing
publishes itself without being read first.

```powershell
python extract_pdf.py                 # PDF -> _raw/YYYY-MM-DD.txt
# ... write _raw/YYYY-MM-DD.json ...
python build_brief.py 2026-10-20      # -> archive/, plus that paper's two aliases
git add et.html et-desk.html archive
git commit -m "Publish 2026-10-20"
git push
```

Pages picks it up in about a minute, plus up to ten minutes of cache.

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

`index.html` is a launcher, not a briefing. It reads the newspaper list out of
`archive/manifest.json` rather than hardcoding it, so a new paper appears by
being built and committed, with no edit to this page. It sends you to the
newspaper you chose last time, on the surface that suits the screen, and only
asks when the choice is genuinely ambiguous — more than one paper, and none
remembered. `ARCHIVE.html` groups by newspaper first and month second, so two
papers on the same day sit side by side instead of interleaving.

**Switching papers from inside an edition.** The top bar carries a newspaper
switcher instead of a "Today" link, and it shows the paper you are reading.
Open it and every paper in the archive is listed with a Laptop and a Phone
link each. It is a native `<details>`, so it opens with a click, works with
scripting off, and closes on an outside click or Escape.

The list is baked in at build time from the manifest, not fetched. A fetched
menu shows an empty box for a frame, fails outright on a `file://` copy with
no server, and cannot work at all in a printed edition. Each link's relative
path is written for the depth the file is about to be saved at, which is why
the build renders the root alias and the archived copy separately instead of
rendering once and copying — a copy drags `../hindu.html` into a file sitting
in the root, where it 404s.

To refresh the public site after a build, commit that paper's aliases and the
archive:

```powershell
git add et.html et-desk.html archive
git commit -m "Publish today's brief"
```

Only those. The extracted article text in `_raw/` stays untracked.

## Extraction notes

`pypdf` reads across columns rather than down them, which is recoverable in
most layouts — headlines, decks and bullet points land next to their own body
text. How well it works is a property of the paper, so it is worth measuring
per paper rather than assuming.

Install with `pip install pypdf`.

**The Economic Times.** Multi-column, and the damage shows. Four of eighteen
pages come out nearly empty, and continuation articles are marked
`From Page 1` — join them before summarising or the story gets attributed to
the wrong headline. Sidebar boxes split from their article; reassign them by
content, not position.

**The Hindu.** Extracts much better. Of 22 pages only four are empty, and those
are masthead and furniture rather than lost content; at 0–6 full-width lines
per page, columns are being read down rather than across. Total artifact count
is 279 in 246,000 characters — 0.1%, and all cosmetic: 21 `/Lnnnn` font
markers, 7 words split at a line break, 2 letter-spaced runs, 241 ligature
glyphs. The same extractor, so this is the layout, not the tool.

Two things survive that the ET PDF never gave us. The front-page `IN BRIEF`
box keeps its **section cross-references** (`EDITORIAL » PAGE 6`,
`WORLD » PAGE 14`), so Categories can carry a real page number instead of a
guess. And **datelines** are intact — `NEW DELHI` seventeen times, plus
Lucknow, Guwahati, Kolkata, Mumbai — so a story's geography is derivable.

One thing does not survive, and it is worth stating plainly: **The Hindu's
section taxonomy is not in the extract.** The running head carries the edition
(`Delhi`, on sixteen of twenty-two pages), not the section, and every other
short all-caps run turned out to be a dateline or a headline kicker. Its
categories cannot be read off the paper, so both newspapers share one list —
`Politics & Governance | Economy & Trade | Business & Markets | Health |
Tech & Society | Sports | Culture & Lifestyle`. A paper-specific taxonomy would
have to be invented, and a shared one means the two briefings are directly
comparable and a term met in one recurs in the other.

The Hindu's Delhi edition also carries little opinion material — one
`Opinion` and three `Editorial` across the whole issue — which is thin for a
briefing that wants three opinion pieces and a long-form read to argue with.

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