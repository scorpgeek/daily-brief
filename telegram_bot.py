"""Telegram bot: receive the issue as a PDF, put it in the repo, let
GitHub Actions do the rest.

    python telegram_bot.py            # poll forever

Forward or upload the newspaper PDF to the bot in Telegram. It lands in
incoming/ and is committed to main, which triggers the workflow.

Stdlib only, so the workflow and this share a dependency-free baseline.

Environment:
    TG_TOKEN    bot token from @BotFather
    GH_TOKEN    a fine-grained token with Contents:write on this repo
    GH_REPO     owner/name, e.g. scorpgeek/daily-brief
    GH_BRANCH   default main

NOTE: the repo is public, so committing the PDF publishes it. If that
matters, use a private holding repo for incoming/ and copy from there.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
INCOMING = os.path.join(HERE, "incoming")
API = "https://api.telegram.org/bot{token}/{method}"

config_error = None
for _k in ("TG_TOKEN", "GH_TOKEN", "GH_REPO"):
    if not os.environ.get(_k):
        config_error = f"{_k} is not set"
        break


def tg(method: str, **params):
    url = API.format(token=os.environ["TG_TOKEN"], method=method)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def reply(chat_id: int, text: str) -> None:
    try:
        tg("sendMessage", chat_id=chat_id, text=text)
    except Exception as e:  # a failed courtesy message must not kill the bot
        print(f"  could not reply: {e}", file=sys.stderr)


def commit(path: str, data: bytes, message: str) -> str:
    """Push one file through the GitHub contents API."""
    import base64
    repo, branch = os.environ["GH_REPO"], os.environ.get("GH_BRANCH", "main")
    api = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "daily-brief-bot",
    }

    req = urllib.request.Request(api, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            sha = json.load(r)["sha"]
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
        sha = None

    payload = {
        "message": message,
        "branch": branch,
        "content": base64.b64encode(data).decode("ascii"),
    }
    if sha:
        payload["sha"] = sha

    req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                 headers={**headers,
                                          "Content-Type": "application/json"},
                                 method="PUT")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)["content"]["html_url"]


def save_doc(doc: dict) -> tuple[str, bytes]:
    url = f"https://api.telegram.org/file/bot{os.environ['TG_TOKEN']}/{doc['file_path']}"
    with urllib.request.urlopen(url, timeout=300) as r:
        data = r.read()
    name = doc.get("file_name") or f"{doc['file_unique_id']}.pdf"
    # the filenames Telegram sends carry superscript digits; keep them, but
    # never depend on a human typing one
    return name, data


def handle(msg: dict) -> None:
    chat = msg.get("chat", {}).get("id")
    doc = (msg.get("document") or {}).get("file", None)
    if not chat or not msg.get("document"):
        reply(chat, "Send the newspaper PDF as a document and I'll build the brief.")
        return

    name, data = save_doc(msg["document"])
    os.makedirs(INCOMING, exist_ok=True)
    path = f"incoming/{name}"
    with open(os.path.join(HERE, path), "wb") as fh:
        fh.write(data)

    url = commit(path, data, f"Incoming: {name}")
    print(f"{name}: {len(data):,} bytes -> {url}")
    reply(chat,
          f"Got {name} ({len(data) // 1024} KB). Building now — "
          f"it'll be at your site in a few minutes.")


def main() -> None:
    if config_error:
        sys.exit(f"telegram_bot: {config_error}. See SETUP-AUTOMATION.md.")

    print("polling Telegram. Ctrl-C to stop.")
    offset = -1
    while True:
        try:
            for update in tg("getUpdates", offset=offset, timeout=50).get("result", []):
                offset = update["update_id"] + 1
                if "message" in update:
                    handle(update["message"])
        except KeyboardInterrupt:
            print("\nstopped")
            return
        except Exception as e:
            print(f"  poll error: {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    main()