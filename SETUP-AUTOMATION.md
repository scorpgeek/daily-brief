# Setting up unattended runs

Four of the five steps already run unattended. `brief_ai.py` is the only
one that needs a model, and this is what puts a model on the other end.

## The chain

```
phone ──forward PDF──> Telegram bot ──commit──> GitHub Actions
                                                      │
                                    extract ─> brief ─> build ─> commit ─> push
                                                      │
                                                  GitHub Pages
```

Nothing runs on your laptop. You forward the PDF from Telegram and read the
result on your phone.

## 1. A model to call with

`brief_ai.py` speaks the OpenAI chat-completions API, so anything with an
OpenAI-compatible endpoint works — OpenAI, Groq, Together, OpenRouter,
LM Studio, Ollama.

One request per issue: about **57k input tokens** (the full article text
plus the spec) producing roughly 8–12k of JSON. Pick something with a large
context window. A small model will not hold the whole paper.

## 2. Repository secrets

Settings → Secrets and variables → Actions → New repository secret.

| Name | Value |
|---|---|
| `DB_API_BASE` | `https://api.openai.com/v1` (or your provider's) |
| `DB_API_KEY` | your key |
| `DB_MODEL` | e.g. `gpt-4o-mini` |
| `DB_PROMPT_B64` | see below |

### The spec secret

`PROMPT.md` is **gitignored on purpose** — it names an employer, a client
account and career goals, and this repo is public. So it travels as a
secret instead:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes("PROMPT.md")) |
  Set-Clipboard
```

Paste that into `DB_PROMPT_B64`. The workflow restores it, then verifies it
looks like the real spec before spending a model call on it.

## 3. The Telegram bot

1. Message **@BotFather** → `/newbot` → copy the token.
2. Settings → Secrets → add `TG_TOKEN`.
3. A **fine-grained** token from GitHub → Settings → Developers → Personal
   access tokens, scoped to this repo with **Contents: read and write**. Add
   it as `GH_TOKEN`.

## 4. Run the bot

It needs somewhere to live, and that somewhere has to be awake. Options:

- **Your laptop**, as a background process or a Task Scheduler job. Simplest
  to try, but it dies when the machine sleeps.
- **A small always-on box** — a spare mini PC, a Raspberry Pi, a cheap VPS.
  This is the one that actually matches "without opening the laptop".

```powershell
$env:TG_TOKEN="..."
$env:GH_TOKEN="..."
$env:GH_REPO="scorpgeek/daily-brief"
python telegram_bot.py
```

## 5. Try it without trusting it

Rehearse the whole chain locally first, with no model call:

```powershell
python daily.py --date 2026-10-19 --skip-brief --no-push
```

That runs extract, build and commit with nothing but the existing JSON. When
you are satisfied, run it once for real with `--no-push` and read the output
before letting anything publish itself.

To force a run from GitHub without sending a PDF: **Actions → daily brief →
Run workflow**.

## What this publishes

The repo is public, so an incoming PDF becomes a public file. The briefings
were already public through Pages; this adds the raw paper and, in the
runner only, the extracted text — which is not committed.

If that matters, point `GH_REPO` at a private holding repo for `incoming/`
and have the workflow fetch from there.

## If a run fails

The **Actions** tab shows the failing step. Two failures are designed:

- *No PROMPT.md and no DB_PROMPT_B64* — the secret is missing or empty.
- *PROMPT.md does not look like the briefing spec* — the base64 was mangled
  in transit; re-copy it.

A model that returns malformed JSON fails in `extract_json` and nothing is
written, so a bad brief never reaches the build. The lints run before the
file is saved, not after.