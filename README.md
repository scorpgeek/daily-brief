# Daily Brief

Turns a newspaper PDF into a single-page, phone-first HTML briefing —
categorised, tagged by importance, with a reading-practice section.

## What it is

A personal reading pipeline:

1. **Extract** — `extract_pdf.py` pulls text out of the PDF, handling the
   subsetted fonts a magazine PDF ships with.
2. **Summarise** — a prompt spec turns the text into a structured briefing
   across 17 sections.
3. **Read** — `TEMPLATE.html` renders it as a collapsible, dark-mode page
   built for a phone, with three bands: quick-use, reference, and language.

The HTML uses three bands so the sections you act on are not buried under
the ones you only reference:

```
USE THESE      Top 5 · My Lens · Shift Huddle Line · Deep Dive · Long-Form Read
REFERENCE      Categories · Numbers · Dates · Client Watch · Verify · Opinion
LANGUAGE       Words · Hindi · Phrases · Traps · Speak · Quiz · Skip List
```

It is self-contained — no build step, no dependencies, no framework.

## Files

```
extract_pdf.py     PDF → _raw/YYYY-MM-DD.txt
TEMPLATE.html      the reading layout (17 sections, 3 bands)
README.md          this file
```

Two files are deliberately **not** in this repo:

- `PROMPT.md` — the briefing spec. It names an employer, a client account and
  career goals, and Pages requires a public repo, so it stays local.
- `_raw/` — extracted article text. Copyrighted.

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
- Dark by default — this is built for reading at night.
- One 120 ms transition on the disclosure chevron, nothing else. Motion in a
  late-night reading document is a cost, not a feature.
- Tables are capped at 4 columns and always preceded by a sentence carrying
  the headline number, so a phone reader who never scrolls still gets it.
- Everything except three sections starts collapsed.