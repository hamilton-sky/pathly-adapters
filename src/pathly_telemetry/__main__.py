"""Entry point: python -m pathly_telemetry  →  runs the MCP telemetry server."""
import sys

# When invoked as the MCP server, all stderr must stay quiet to avoid
# polluting the JSON-RPC stream. Redirect stderr to a log file.
from pathlib import Path

_log = Path.home() / ".pathly" / "telemetry.log"
_log.parent.mkdir(parents=True, exist_ok=True)
sys.stderr = open(_log, "a", encoding="utf-8", buffering=1)  # noqa: WPS515

from .server import run  # noqa: E402

run()
