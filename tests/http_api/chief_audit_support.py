"""Watch what the server does to the disk while a chief sends it hostile requests
(chief-agent 08, round 6).

``sys.addaudithook`` reports the file system calls Python makes (``open``, ``os.mkdir``,
``os.rename``, ``os.remove``, ``shutil.*``, ``sqlite3.connect``, a child process's working
directory, ...) whatever code makes them, so a sink nobody listed is seen too. ``Audit`` records
each one that names a path and counts the ones that fall in a zone the chief's project does not
own: another project's tree, the server's working directory, the home directory.

What it cannot see: ``os.stat``, ``os.path.exists`` and the like are not audit events, so a probe
for a file's existence is invisible; neither is a write the C layer of a library makes (sqlite is
seen only at ``sqlite3.connect``); a path rebuilt in a child process is seen only by its working
directory; and ``os.open`` with a ``dir_fd`` (what ``shutil.rmtree`` does to go down into a
subdirectory) raises an ``open`` event that does not carry the descriptor, so its relative path
is read against the working directory: counted, at the wrong path. Every other call that takes a
``dir_fd`` is read against the directory it names. A hook cannot be removed once added, so it is installed once and does nothing unless an
``Audit`` is active.
"""

from __future__ import annotations

import os
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

try:
    import fcntl
except ImportError:  # Windows: no dir_fd calls to resolve
    fcntl = None

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
# audit event -> {position of a path argument: position of the dir_fd it is relative to}. A
# relative path with a dir_fd names a file in that directory, not in the working directory
# (``shutil.rmtree`` removes the entries of a tree this way). The target of ``os.symlink`` (0)
# is the text the link holds, so only the link itself (1) is read against its dir_fd.
_DIR_FD_ARGUMENTS = {
    "os.mkdir": {0: 2},
    "os.rename": {0: 2, 1: 3},
    "os.remove": {0: 1},
    "os.rmdir": {0: 1},
    "os.symlink": {1: 2},
    "os.link": {0: 2, 1: 3},
    "os.chmod": {0: 2},
    "os.chown": {0: 3},
    "os.utime": {0: 3},
    "shutil.rmtree": {0: 1},
}


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
        dir_fds = _DIR_FD_ARGUMENTS.get(event, {})
        for position in wanted:
            raw = _argument(args, position)
            if raw is None and event not in _DEFAULT_TO_CWD:
                continue
            path = _absolute(raw, _argument(args, dir_fds.get(position)))
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


def _argument(args: tuple, position: int | None) -> object:
    return args[position] if position is not None and position < len(args) else None


def _fd_path(fd: int) -> str | None:
    """The path an open descriptor names, or None when the platform cannot say."""
    try:
        if fcntl is not None and hasattr(
            fcntl, "F_GETPATH"
        ):  # macOS: MAXPATHLEN is 1024
            raw = fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024))
            return os.fsdecode(raw.split(b"\0", 1)[0]) or None
        return os.readlink(f"/proc/self/fd/{fd}")
    except Exception:
        return None


def _absolute(raw: object, dir_fd: object = None) -> str | None:
    """The real absolute path an audit argument names: a relative path is read against
    ``dir_fd`` when the call names one, else against the working directory, and a descriptor is
    read as the file it is open on. None for a value that is not a path, or a descriptor the
    platform cannot name (a pipe, a socket). A ``dir_fd`` it cannot name leaves the path read
    against the working directory, the server's, so the call is still counted. Never raises: a
    hook that raises breaks the call it watches.
    """
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = os.fsdecode(raw)
        elif isinstance(raw, os.PathLike):
            raw = os.fspath(raw)
        if raw is None:
            raw = "."
        if isinstance(raw, int) and not isinstance(raw, bool):
            raw = _fd_path(raw)
        if not isinstance(raw, str):
            return None
        base = None
        if isinstance(dir_fd, int) and not isinstance(dir_fd, bool) and dir_fd >= 0:
            base = _fd_path(dir_fd)  # -1 (none) and AT_FDCWD (negative) are the cwd
        joined = os.path.join(base or os.getcwd(), raw)
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
