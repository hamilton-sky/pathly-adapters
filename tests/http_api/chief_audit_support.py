"""Watch what the server does to the disk while a chief sends it hostile requests
(chief-agent 08, round 6).

``sys.addaudithook`` reports the file system calls Python makes (``open``, ``os.mkdir``,
``os.rename``, ``os.remove``, ``shutil.*``, ``sqlite3.connect``, a child process's working
directory, ...) whatever code makes them, so a sink nobody listed is seen too. ``Audit`` records
each one that names a path and counts the ones that fall in a zone the chief's project does not
own: another project's tree, the server's working directory, the home directory.

What it cannot see: ``os.stat``, ``os.path.exists`` and the like are not audit events, so a probe
for a file's existence is invisible; neither is a write the C layer of a library makes (sqlite is
seen only at ``sqlite3.connect``); and a path rebuilt in a child process is seen only by its working
directory. A hook cannot be removed once added, so it is installed once and does nothing unless an
``Audit`` is active.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

# audit event -> the positions of its arguments that are paths
_PATH_ARGUMENTS = {
    "open": (0,),
    "os.mkdir": (0,),
    "os.rename": (0, 1),
    "os.remove": (0,),
    "os.rmdir": (0,),
    "os.symlink": (0, 1),
    "os.link": (0, 1),
    "os.truncate": (0,),
    "os.chmod": (0,),
    "os.chown": (0,),
    "os.utime": (0,),
    "os.listdir": (0,),
    "os.scandir": (0,),
    "os.chdir": (0,),
    "os.walk": (0,),
    "shutil.copyfile": (0, 1),
    "shutil.copymode": (0, 1),
    "shutil.copystat": (0, 1),
    "shutil.copytree": (0, 1),
    "shutil.move": (0, 1),
    "shutil.rmtree": (0,),
    "glob.glob": (0,),
    "sqlite3.connect": (0,),
    "tempfile.mkdtemp": (0,),
    "tempfile.mkstemp": (0,),
    "subprocess.Popen": (2,),  # (executable, args, cwd, env): the working directory
}
# These name the working directory when they are given nothing.
_DEFAULT_TO_CWD = {"os.listdir", "os.scandir", "os.walk"}


@dataclass(frozen=True)
class Touch:
    event: str
    path: str
    label: str


@dataclass
class Audit:
    """The zones of one test and what the server did in them."""

    allowed: tuple[str, ...]
    forbidden: tuple[str, ...]
    label: str = ""
    seen: list[Touch] = field(default_factory=list)
    violations: list[Touch] = field(default_factory=list)

    def under(self, path: str, roots: tuple[str, ...]) -> bool:
        return any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)

    def record(self, event: str, args: tuple) -> None:
        wanted = _PATH_ARGUMENTS.get(event)
        if wanted is None:
            return
        for position in wanted:
            raw = args[position] if position < len(args) else None
            if raw is None and event not in _DEFAULT_TO_CWD:
                continue
            path = _absolute(raw)
            if path is None or _is_pseudo_file(event, raw, path):
                continue
            touch = Touch(event, path, self.label)
            if self.under(path, self.allowed):
                self.seen.append(touch)
            elif self.under(path, self.forbidden):
                self.violations.append(touch)

    def __enter__(self) -> "Audit":
        global _active
        _install()
        _active = self
        return self

    def __exit__(self, *exc) -> None:
        global _active
        _active = None


def _absolute(raw: object) -> str | None:
    """The real absolute path an audit argument names; None for a file descriptor or a value
    that is not a path. Never raises: a hook that raises breaks the call it watches.
    """
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = os.fsdecode(raw)
        elif isinstance(raw, os.PathLike):
            raw = os.fspath(raw)
        if raw is None:
            raw = "."
        if not isinstance(raw, str):
            return None
        joined = os.path.join(os.getcwd(), raw)
        try:
            return os.path.realpath(joined)
        except ValueError:  # an embedded NUL: nothing for the kernel to resolve
            return os.path.normpath(joined)
    except Exception:
        return None


def _is_pseudo_file(event: str, raw: object, path: str) -> bool:
    """True for an ``open`` of a name like ``<unknown>`` that names no file.

    CPython names code it compiles from a string ``<string>`` or ``<unknown>``, and a syntax error
    in that code makes it open the name to quote the offending line. Python 3.13's traceback
    formatting compiles source fragments, so the server logging an exception does this in the
    working directory (the server's). The open finds nothing and reads nothing; a file that really
    exists under such a name is still reported.
    """
    return (
        event == "open"
        and isinstance(raw, str)
        and raw.startswith("<")
        and raw.endswith(">")
        and not os.path.lexists(path)
    )


_active: Audit | None = None
_installed = False
_install_lock = threading.Lock()


def _hook(event: str, args: tuple) -> None:
    audit = _active
    if audit is None or event not in _PATH_ARGUMENTS:
        return
    try:
        audit.record(event, args)
    except Exception:
        pass


def _install() -> None:
    global _installed
    with _install_lock:
        if not _installed:
            sys.addaudithook(_hook)
            _installed = True


def zones(project: Path, other: Path, server: Path, home: Path) -> Audit:
    """The audit of a sandbox: the chief's ``project`` and ``~/.pathly`` are its own; another
    project, the server's working directory and the home directory are not.

    ``home`` is what ``Path.home()`` answers in the test (the product code reads no other: the
    only ``expanduser`` in the package is on a route no chief reaches). The user's real home is
    not a zone, because the repository and the Python install may lie inside it.
    """
    allowed = (str(project.resolve()), str((home / ".pathly").resolve()))
    forbidden = tuple(str(p.resolve()) for p in (other, server, home))
    return Audit(allowed=allowed, forbidden=forbidden)
