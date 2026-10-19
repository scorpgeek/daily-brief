"""Test the model-output handling in brief_ai.py.

The model is told to return one JSON object and nothing else. Models
mostly comply. Mostly is the operative word, so extract_json has to cope
with fences and leading prose, and validate has to reject a brief the
build would refuse -- otherwise a bad brief gets written and the failure
surfaces three steps later as a confusing build error.
"""

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import brief_ai  # noqa: E402

fails = []


def ok(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{'' if cond else '  ' + detail}")
    if not cond:
        fails.append(name)


BRIEF = json.load(open(os.path.join(HERE, "_raw", "2026-10-19.json"),
                       encoding="utf-8"))
CLEAN = json.dumps(BRIEF, ensure_ascii=False)

print("extract_json")

got = brief_ai.extract_json(CLEAN)
ok("bare JSON", got["meta"]["date"] == "2026-10-19")

got = brief_ai.extract_json("```json\n" + CLEAN + "\n```")
ok("fenced with language", got["meta"]["date"] == "2026-10-19")

got = brief_ai.extract_json("```\n" + CLEAN + "\n```")
ok("fenced without language", got["meta"]["date"] == "2026-10-19")

got = brief_ai.extract_json(
    "Here is the brief you asked for:\n\n" + CLEAN + "\n\nLet me know if you "
    "want section 9 expanded.")
ok("prose before and after", got["meta"]["date"] == "2026-10-19")

got = brief_ai.extract_json('  \n' + CLEAN.replace('"deflation"', '"say \\"hi\\" deflation"') + '  \n')
ok("escaped quotes inside strings survive",
   any("hi" in (w.get("mine", "") + w.get("meaning", ""))
       for w in got.get("words", [])))

for name, bad in [("empty", ""), ("no object", "I cannot do that."),
                  ("truncated", CLEAN[:len(CLEAN) // 2])]:
    try:
        brief_ai.extract_json(bad)
        ok(f"rejects {name}", False, "returned instead of raising")
    except (ValueError, json.JSONDecodeError):
        ok(f"rejects {name}", True)

print("\nvalidate")

brief_ai.validate(BRIEF)
ok("accepts the hand-written brief", True)

broken = json.loads(CLEAN)
broken["terms"][0]["exp"] = broken["terms"][0]["term"]
try:
    brief_ai.validate(broken)
    ok("rejects exp that echoes its term", False, "accepted")
except SystemExit:
    ok("rejects exp that echoes its term", True)

broken = json.loads(CLEAN)
del broken["quiz"][0]["opts"]
try:
    brief_ai.validate(broken)
    ok("rejects a quiz with no options", False, "accepted")
except SystemExit:
    ok("rejects a quiz with no options", True)

print(f"\n{'all passed' if not fails else str(len(fails)) + ' failed'}")
sys.exit(1 if fails else 0)