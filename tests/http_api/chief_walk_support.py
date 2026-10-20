"""Reading the source of a route's view and the helpers it calls (chief-agent 08).

Shared by the tests that check ``chief_fields.ROUTE_FIELDS`` against the code: the table test
(the walk reaches the helpers) and the key tests (a key a view reads is listed, or deliberately
not). ``request_keys_read`` finds the keys a function reads from the request by what the name is
bound to (``read_json_body()``, ``request.get_json()``, ``request.args``, a ``body`` or ``data``
parameter), not by what the key is called, so a ``flow`` or a ``skill`` is seen like a ``scope``.
``keys_joined_into_paths`` follows a key one step further, inside the function that reads it: into
the names assigned from it and into the arguments of a call that makes or opens a path.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import textwrap

HELPER_PACKAGE = "pathly_orchestrator.http_server.blueprints"
# Outside ``blueprints/``, the one module a view hands the request's body to: the answer routes
# read ``answer`` through ``chief_cite.answer_text(data)`` (chief-agent 10).
BODY_HELPER_MODULES = ("pathly_orchestrator.http_server.chief_cite",)
# A helper takes the request's body under one of these parameter names.
BODY_PARAMETERS = {"body", "data"}
_READERS = {"read_json_body", "get_json"}
_GETTERS = {"get", "getlist"}


def _is_helper_module(module: str) -> bool:
    return module.startswith(HELPER_PACKAGE) or module in BODY_HELPER_MODULES


def called_functions(function):
    """The functions under ``blueprints/`` (and in ``BODY_HELPER_MODULES``) that ``function``
    calls by name: a module-level name, or one it imports inside its body (the layer rule keeps
    the imports lazy).
    """
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    except (OSError, TypeError):
        return
    package = function.__module__.rpartition(".")[0]
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = importlib.util.resolve_name(
                "." * node.level + (node.module or ""), package
            )
            for alias in node.names:
                imported[alias.asname or alias.name] = (module, alias.name)
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    for name in called:
        if name in imported:
            module, attr = imported[name]
            target = (
                getattr(importlib.import_module(module), attr, None)
                if _is_helper_module(module)
                else None
            )
        else:
            target = function.__globals__.get(name)
        if inspect.isfunction(target) and _is_helper_module(target.__module__):
            yield target


def view_and_helpers(app, rule_text: str, method: str):
    """``(function, source)`` for each view of the route and every helper it calls (3 levels)."""
    seen: set = set()

    def walk(function, depth):
        if function in seen or depth < 0:
            return
        seen.add(function)
        try:
            yield function, textwrap.dedent(inspect.getsource(function))
        except (OSError, TypeError):
            return
        for helper in called_functions(function):
            yield from walk(helper, depth - 1)

    for rule in app.url_map.iter_rules():
        if rule.rule == rule_text and method in rule.methods:
            yield from walk(inspect.unwrap(app.view_functions[rule.endpoint]), 3)


def _is_request_args(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "args"
        and isinstance(node.value, ast.Name)
        and node.value.id == "request"
    )


def _reads_the_request(value: ast.AST) -> bool:
    """True for an expression that is the request's body or query string (or one of them
    ``or`` a default): ``read_json_body()``, ``request.get_json(...)``, ``request.args``.
    """
    if isinstance(value, ast.BoolOp):
        return any(_reads_the_request(v) for v in value.values)
    if _is_request_args(value):
        return True
    if isinstance(value, ast.Call):
        func = value.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        return name in _READERS
    return False


def _string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def request_keys_read(source: str, parameters: bool) -> set[str]:
    """The keys the function in ``source`` reads from the request.

    A container is a name assigned the request's body or query string, or (``parameters`` true,
    for a helper) a parameter called ``body`` or ``data``. A read is ``container.get("k")``,
    ``container.getlist("k")``, ``container["k"]``, ``"k" in container``, or the same on
    ``request.args``.
    """
    tree = ast.parse(source)
    containers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _reads_the_request(node.value):
            containers.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.arguments) and parameters:
            containers.update(a.arg for a in node.args if a.arg in BODY_PARAMETERS)

    def is_container(node: ast.AST) -> bool:
        return _is_request_args(node) or (
            isinstance(node, ast.Name) and node.id in containers
        )

    found: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _GETTERS
            and is_container(node.func.value)
            and node.args
        ):
            key = _string(node.args[0])
        elif isinstance(node, ast.Subscript) and is_container(node.value):
            key = _string(node.slice)
        elif (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and isinstance(node.ops[0], ast.In)
            and is_container(node.comparators[0])
        ):
            key = _string(node.left)
        else:
            continue
        if key is not None:
            found.add(key)
    return found


def view_keys_read(app, rule_text: str, method: str) -> dict[str, set[str]]:
    """``{function name: keys}`` for the view of the route and the helpers it calls."""
    out: dict[str, set[str]] = {}
    for index, (function, source) in enumerate(
        view_and_helpers(app, rule_text, method)
    ):
        keys = request_keys_read(source, parameters=index > 0)
        if keys:
            out[function.__name__] = keys
    return out


# --- where a key goes inside the function that reads it ----------------------------------------

# A call that makes, opens or measures a path. A bare last segment is enough for the distinctive
# names; the ones a string method shares (``replace``, ``join``) must be spelled in full.
_PATH_CALL_TAILS = {
    "open",
    "Path",
    "PurePath",
    "PurePosixPath",
    "PureWindowsPath",
    "makedirs",
    "mkdir",
    "listdir",
    "scandir",
    "rmtree",
    "copytree",
    "copyfile",
    "unlink",
    "iglob",
    "_resolve_storage_path",
    "safe_artifact_path",
}
_PATH_CALL_NAMES = {
    "os.path.join",
    "posixpath.join",
    "os.path.abspath",
    "os.path.realpath",
    "os.path.exists",
    "os.path.isfile",
    "os.path.isdir",
    "os.walk",
    "os.remove",
    "os.rename",
    "os.replace",
    "os.rmdir",
    "glob.glob",
    "shutil.copy",
    "shutil.move",
}


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _is_path_call(call: ast.Call) -> bool:
    name = _dotted(call.func)
    return name in _PATH_CALL_NAMES or name.rpartition(".")[2] in _PATH_CALL_TAILS


def keys_joined_into_paths(source: str, parameters: bool) -> set[tuple[str, str]]:
    """``(key, call)`` for each request key the function in ``source`` reads and then passes,
    directly or through the names it is assigned to, to a call that makes or opens a path (or
    divides a ``Path`` by it).

    Inside one function only: a key handed to another function is followed only when that
    function is itself one of the helpers the walk reaches and takes it as ``body`` or ``data``.
    Calls outside ``_PATH_CALL_NAMES`` and ``_PATH_CALL_TAILS`` are not paths to it.
    """
    tree = ast.parse(source)
    containers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _reads_the_request(node.value):
            containers.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.arguments) and parameters:
            containers.update(a.arg for a in node.args if a.arg in BODY_PARAMETERS)

    def is_container(node: ast.AST) -> bool:
        return _is_request_args(node) or (
            isinstance(node, ast.Name) and node.id in containers
        )

    def key_read(node: ast.AST) -> str | None:
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _GETTERS
            and is_container(node.func.value)
            and node.args
        ):
            return _string(node.args[0])
        if isinstance(node, ast.Subscript) and is_container(node.value):
            return _string(node.slice)
        return None

    tainted: dict[str, set[str]] = {}

    def keys_in(expression: ast.AST) -> set[str]:
        found: set[str] = set()
        for node in ast.walk(expression):
            key = key_read(node)
            if key is not None:
                found.add(key)
            if isinstance(node, ast.Name):
                found |= tainted.get(node.id, set())
        return found

    changed = True
    while changed:  # a name assigned from a name assigned from a key
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value:
                targets, value = [node.target], node.value
            else:
                continue
            keys = keys_in(value)
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name) and not keys <= tainted.get(
                        name.id, set()
                    ):
                        tainted.setdefault(name.id, set()).update(keys)
                        changed = True

    joined: set[tuple[str, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _is_path_call(node):
            for argument in [*node.args, *(k.value for k in node.keywords)]:
                joined |= {(k, _dotted(node.func)) for k in keys_in(argument)}
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            joined |= {(k, "/") for k in keys_in(node)}
    return joined


def view_keys_joined_into_paths(app, rule_text: str, method: str):
    """``{(function name, key, call)}`` for the view of the route and the helpers it calls."""
    found = set()
    for index, (function, source) in enumerate(
        view_and_helpers(app, rule_text, method)
    ):
        for key, call in keys_joined_into_paths(source, parameters=index > 0):
            found.add((function.__name__, key, call))
    return found
