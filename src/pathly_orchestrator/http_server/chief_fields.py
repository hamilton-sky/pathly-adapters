"""Which request fields each route reads, for the chief gate (chief-agent).

``ROUTE_ACTIONS`` (``chief_routes``) says what a call is. ``ROUTE_FIELDS`` says what it *reads*:
for every route a chief token can get past the route table, the keys of its body (or query
string), the project root, board scope, file, flow or skill each one names, and the ids it
leaves unbound. The gate applies an entry with ``chief_project.project_refusal`` (which project
the request names) and ``chief_keys.key_refusal`` (which keys it may send), so a route that reads
a new key is one table entry, not another branch. ``tests/http_api/test_chief_gate_tables.py``
walks ``app.url_map`` and fails when a route the chief can reach has no entry, and
``test_chief_gate_keys.py`` reads the views for a key no entry lists.

The table is in two files by what a route reads: ``chief_field_calls`` (the POST calls the route
table lists, which read a JSON body) and ``chief_field_reads`` (every GET the gate lets through,
which read the query string). ``chief_field_types`` says what an entry can say.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .chief_field_calls import CALL_FIELDS
from .chief_field_reads import READ_FIELDS
from .chief_field_types import Fields

ROUTE_FIELDS: Mapping[tuple[str, str], Fields] = MappingProxyType(
    {**CALL_FIELDS, **READ_FIELDS}
)
