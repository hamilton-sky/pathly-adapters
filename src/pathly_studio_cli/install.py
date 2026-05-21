"""pathly-studio install — download and install Pathly Studio from GitHub Releases."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

_REPO = "hamilton-sky/pathly-adapters"
_API = f"https://api.github.com/repos/{_REPO}/releases/latest"


def _latest_release() -> dict:
    req = urllib.request.Request(
        _API, headers={"Accept": "application/vnd.github+json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def _find_asset(assets: list[dict]) -> dict | None:
    plat = sys.platform
    for asset in assets:
        name = asset["name"].lower()
        if plat == "win32" and name.endswith(".exe"):
            return asset
        if plat == "darwin" and name.endswith(".dmg"):
            return asset
        if plat.startswith("linux") and name.endswith(".appimage"):
            return asset
    return None


def _download(url: str, dest: Path) -> None:
    print(f"Downloading {url} …")
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=120) as r:
        total = int(r.getheader("Content-Length", 0))
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = r.read(65536)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if total:
                    pct = done * 100 // total
                    print(
                        f"\r  {pct}%  ({done // 1024 // 1024} MB)", end="", flush=True
                    )
    print()


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Install Pathly Studio desktop app")
    p.add_argument(
        "command", choices=["install", "version"], nargs="?", default="install"
    )
    args = p.parse_args()

    if args.command == "version":
        try:
            rel = _latest_release()
            print(f"Latest release: {rel['tag_name']}")
        except Exception as exc:
            print(f"Could not fetch release info: {exc}", file=sys.stderr)
            sys.exit(1)
        return

    print("Fetching latest Pathly Studio release…")
    try:
        rel = _latest_release()
    except Exception as exc:
        print(f"ERROR: Could not reach GitHub Releases: {exc}", file=sys.stderr)
        print(
            "Download manually from: https://github.com/hamilton-sky/pathly-adapters/releases"
        )
        sys.exit(1)

    tag = rel["tag_name"]
    assets: list[dict] = rel.get("assets", [])
    asset = _find_asset(assets)

    if not asset:
        print(
            f"No Studio installer found in release {tag} for platform {sys.platform}."
        )
        print(
            "Download manually from: https://github.com/hamilton-sky/pathly-adapters/releases"
        )
        sys.exit(1)

    print(f"Found: {asset['name']} ({asset['size'] // 1024 // 1024} MB)")

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / asset["name"]
        _download(asset["browser_download_url"], dest)

        print("Running installer…")
        if sys.platform == "win32":
            subprocess.run([str(dest)], check=True)
        elif sys.platform == "darwin":
            mount_out = subprocess.check_output(
                ["hdiutil", "attach", str(dest), "-nobrowse", "-readonly"], text=True
            )
            mount_point = [
                line.split("\t")[-1].strip()
                for line in mount_out.splitlines()
                if "/Volumes/" in line
            ][-1]
            app_src = next(Path(mount_point).glob("*.app"))
            dest_app = Path("/Applications") / app_src.name
            print(f"Installing to {dest_app} …")
            if dest_app.exists():
                subprocess.run(["rm", "-rf", str(dest_app)], check=True)
            subprocess.run(["cp", "-R", str(app_src), str(dest_app)], check=True)
            subprocess.run(["hdiutil", "detach", mount_point], check=True)
            print(f"Installed to {dest_app}")
        else:
            install_path = Path.home() / ".local" / "bin" / "pathly-studio-app"
            install_path.parent.mkdir(parents=True, exist_ok=True)
            dest.rename(install_path)
            install_path.chmod(
                install_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
            )
            print(f"Installed to {install_path}")
            print("Run:  pathly-studio-app")

    print("Done. Pathly Studio installed.")
