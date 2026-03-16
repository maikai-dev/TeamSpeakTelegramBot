from __future__ import annotations

import argparse
import os
import sys

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Пример внешнего voice-worker для TS3")
    sub = parser.add_subparsers(dest="command", required=True)

    join = sub.add_parser("join")
    join.add_argument("--channel", type=int, required=True)

    play = sub.add_parser("play")
    play.add_argument("--channel", type=int, required=True)
    play.add_argument("--text", type=str, required=True)
    play.add_argument("--audio", type=str, required=True)

    sub.add_parser("leave")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoint = os.getenv("VOICE_WORKER_HTTP_ENDPOINT")

    payload = {"command": args.command}
    if args.command in {"join", "play"}:
        payload["channel"] = args.channel
    if args.command == "play":
        payload["text"] = args.text
        payload["audio"] = args.audio

    if endpoint:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(endpoint, json=payload)
            response.raise_for_status()
        print(f"voice worker: command '{args.command}' sent to {endpoint}")
        return 0

    if os.getenv("VOICE_DRY_RUN", "1") == "1":
        print(f"[DRY-RUN] {payload}")
        return 0

    print(
        "VOICE_WORKER_HTTP_ENDPOINT не задан и VOICE_DRY_RUN=0. "
        "Подключите реальный sidecar и повторите.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
