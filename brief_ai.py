"""Step 3 of the daily chain: turn extracted article text into a brief.

The only step that is not already a script. Everything else -- extract,
build, publish -- runs unattended. This calls a model, and gets back the
same JSON that build_brief.py consumes.

    python brief_ai.py 2026-10-19
    python brief_ai.py 2026-10-19 --dry-run   # assemble, report, no call
    python brief_ai.py --self-test             # check a hand-written brief

Configuration is by environment variable, and the client is
OpenAI-compatible so it works against OpenAI, Groq, Together, Ollama,
LM Studio, or whatever OpenCode is already pointed at:

    DB_API_BASE   e.g. https://api.openai.com/v1
    DB_API_KEY    your key
    DB_MODEL      e.g. gpt-4o-mini
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "_raw")
PROMPT = os.path.join(HERE, "PROMPT.md")

SYSTEM = """You are producing a daily newspaper briefing for an operations \
manager in a BPO and telecom account. You follow the briefing spec exactly \
and you are ruthlessly honest about what the paper does and does not say.

Hard rules:
- News facts come only from the supplied article text. Never invent a \
figure, a name, a date, or a quotation.
- If the paper does not support something, say so rather than filling the gap.
- Return one JSON object and nothing else. No prose before or after it, no \
markdown fences.
- Every field in the shape below must be present.

The shape, verbatim:

%s

The extracted article text follows."""


def load_text(stem: str) -> str:
    path = os.path.join(RAW, stem + ".txt")
    if not os.path.exists(path):
        sys.exit(f"no extracted text for {stem} -- run extract_pdf.py first")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def load_spec() -> str:
    if not os.path.exists(PROMPT):
        sys.exit("PROMPT.md not found -- it is gitignored, so it must be "
                 "present locally for this step")
    with open(PROMPT, encoding="utf-8") as fh:
        return fh.read()


def shape_from_spec(spec: str) -> str:
    """Pull the JSON shape out of the spec so the two cannot drift."""
    start = spec.find("const BRIEF = {")
    if start == -1:
        # fall back to the whole spec; it is short enough and the model can
        # find the shape itself
        return spec
    end = spec.find("\n}", start)
    return spec[start:end + 2] if end != -1 else spec[start:start + 2000]


def extract_json(text: str) -> dict:
    """Models sometimes wrap JSON in prose or fences despite being told not
    to. Take the outermost brace-balanced span rather than trusting either."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object in the model output")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unbalanced JSON in the model output")


def call_model(spec: str, text: str, *, timeout: int = 900) -> str:
    base = os.environ.get("DB_API_BASE", "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get("DB_API_KEY", "")
    model = os.environ.get("DB_MODEL", "")
    if not key or not model:
        sys.exit("set DB_API_KEY and DB_MODEL (and DB_API_BASE if not OpenAI)")

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system",
             "content": SYSTEM % shape_from_spec(spec)},
            {"role": "user",
             "content": f"Produce the brief for this issue.\n\n{text}"},
        ],
        "temperature": 0.2,
        "max_tokens": 32000,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        sys.exit(f"model call failed: HTTP {e.code}\n{detail}")
    except urllib.error.URLError as e:
        sys.exit(f"could not reach {base}: {e.reason}")

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        sys.exit("unexpected response shape from the model:\n"
                 + json.dumps(data)[:600])


def validate(brief: dict) -> None:
    """Run the same lints the build runs, before the build does."""
    import build_brief
    for name in ("lint_terms", "lint_quiz"):
        fn = getattr(build_brief, name, None)
        if fn:
            fn(brief)


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    dry = "--dry-run" in sys.argv

    if not args:
        sys.exit(__doc__)
    stem = args[0]

    text = load_text(stem)
    spec = load_spec()
    shape = shape_from_spec(spec)

    print(f"{stem}: {len(text):,} chars of article text")
    print(f"  spec   {len(spec):,} chars, shape {len(shape):,} chars")
    print(f"  approx {int(len(text) / 3.6):,} input tokens")

    if dry:
        print("\n--dry-run: nothing sent, nothing written.")
        return

    out = call_model(spec, text)
    brief = extract_json(out)
    print(f"  model returned {len(out):,} chars")

    for key in ("meta", "top"):
        if key not in brief:
            sys.exit(f"brief is missing {key!r} -- refusing to write it")

    validate(brief)
    print("  lints passed")

    path = os.path.join(RAW, stem + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(brief, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print(f"  wrote {os.path.basename(path)}")


if __name__ == "__main__":
    main()