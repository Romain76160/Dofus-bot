#!/usr/bin/env python3
"""Forward decoded JSONL events to the local FastAPI observer."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import TextIO


def open_lines(source: str) -> TextIO:
    if source == "-":
        return sys.stdin
    return Path(source).open("r", encoding="utf-8")


def normalize(obj: dict) -> dict:
    if "payload" in obj:
        return obj
    return {
        "message_type": "unknown",
        "direction": "unknown",
        "payload": obj,
    }


def post_json(url: str, payload: object) -> object:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def send_batch(base_url: str, events: list[dict]) -> int:
    if not events:
        return 0

    if len(events) == 1:
        result = post_json(f"{base_url}/api/network/ingest", events[0])
        applied = result.get("applied", {}) if isinstance(result, dict) else {}
        if applied:
            print(f"applied {applied}")
        return 1

    result = post_json(f"{base_url}/api/network/ingest-batch", events)
    if isinstance(result, dict):
        print(
            f"batch: received={result.get('received', len(events))} "
            f"applied={result.get('applied_events', 0)}"
        )
    return len(events)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="JSONL file or '-' for stdin")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="FastAPI base URL",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=25,
        help="Number of events per HTTP request (1-500)",
    )
    args = parser.parse_args()
    batch_size = max(1, min(args.batch_size, 500))

    sent = 0
    pending: list[dict] = []

    try:
        with open_lines(args.source) as stream:
            for line_no, raw in enumerate(stream, start=1):
                raw = raw.strip()
                if not raw:
                    continue

                try:
                    obj = json.loads(raw)
                    if not isinstance(obj, dict):
                        raise ValueError("each JSONL line must contain an object")
                    pending.append(normalize(obj))

                    if len(pending) >= batch_size:
                        sent += send_batch(args.base_url.rstrip("/"), pending)
                        pending.clear()
                except (json.JSONDecodeError, ValueError) as exc:
                    print(f"[{line_no}] skipped: {exc}", file=sys.stderr)

            sent += send_batch(args.base_url.rstrip("/"), pending)
    except urllib.error.URLError as exc:
        print(f"backend unavailable: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        pass

    print(f"forwarded {sent} event(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
