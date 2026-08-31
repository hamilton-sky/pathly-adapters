"""``pathly-pty-host`` — run the headless spawn host in the foreground."""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from .host import DEFAULT_MAX_CONCURRENT, SpawnHost


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pathly-pty-host",
        description=(
            "Spawn CLI agents for a Pathly run without Studio. Subscribes to the FSM "
            "server's /events/spawn stream, runs each TERMINAL_SPAWN as a subprocess, and "
            "reports the result back — the same contract Studio's Electron host implements. "
            "Run exactly one host at a time."
        ),
    )
    parser.add_argument("--host", default="127.0.0.1", help="FSM server host")
    parser.add_argument("--port", type=int, default=8765, help="FSM server port")
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=DEFAULT_MAX_CONCURRENT,
        help=f"Concurrent CLI spawns (default {DEFAULT_MAX_CONCURRENT}); further spawns queue.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log every spawn decision at DEBUG.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.max_concurrent < 1:
        print("ERROR: --max-concurrent must be at least 1", file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    host = SpawnHost(host=args.host, port=args.port, max_concurrent=args.max_concurrent)

    def _shutdown(_signum: int, _frame: object) -> None:
        logging.getLogger("pathly.pty_host").info("pty_host: shutting down")
        host.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, OSError):
            pass  # not the main thread, or unsupported on this platform

    try:
        host.run()
    except KeyboardInterrupt:
        host.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
