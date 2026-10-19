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
build_brief.py   _raw/YYYY-MM-DD.json -> YYYY-MM-DD.html        (phone)
                                           YYYY-MM-DD-desk.html  (laptop)
```

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

The external-sourced material is always labelled. Nothing web-sourced is
allowed into a news section; it appears only in the glossary and the
`Context` blocks, which carry their own source lists.

## Files

```
extract_pdf.py     PDF -> _raw/YYYY-MM-DD.txt
build_brief.py     _raw/YYYY-MM-DD.json -> both HTML editions
_tpl/phone.html    phone template  (markers: <!--SECTIONS-->)
_tpl/desk.html     laptop template (markers: <!--SECTIONS-->, /*GLOSSARY*/)
index.html         published phone sample
DESK.html          published laptop sample
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

Serve locally and open on a phone on the same network:

```powershell
python -m http.server 8899 --bind 0.0.0.0
```

Then `http://<your-ip>:8899/`.

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
- Dark by default — this is built for reading at night. A warm-paper light
  theme sits alongside it, toggled from the top bar or the rail; the choice
  persists.
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
- One 120 ms transition on the disclosure chevron, nothing else. Motion in a
  late-night reading document is a cost, not a feature.
- Tables are capped at 4 columns and always preceded by a sentence carrying
  the headline number, so a phone reader who never scrolls still gets it.
- Part-of-speech is shown in the laptop vocab table and hidden on the phone,
  where it would break the measure.