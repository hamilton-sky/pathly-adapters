from pathlib import Path

_HOST_MARKERS: dict[str, list[Path]] = {
    "claude": [
        Path.home() / ".claude",
    ],
    "codex": [
        Path.home() / ".codex",
        Path.home() / ".openai-codex",
    ],
    "copilot": [
        Path.home() / "AppData" / "Roaming" / "Code",          # Windows
        Path.home() / ".config" / "Code",                       # Linux
        Path.home() / "Library" / "Application Support" / "Code",  # macOS
        Path.home() / ".vscode",
    ],
}


def detect_hosts() -> list[str]:
    return [host for host, paths in _HOST_MARKERS.items() if any(p.exists() for p in paths)]
