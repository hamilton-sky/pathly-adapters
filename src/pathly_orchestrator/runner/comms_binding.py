"""What "binding" means for a board row, in one place.

A binding decision (``binding = 1``) is a standing order. Three modules ask about it:
``comms_governance`` (which rows are orders, and which pending rows are not), ``comms_formatters``
(which rows render as orders) and ``comms_context`` (which rows stay out of the Context channel).
This leaf module imports nothing from the package, so none of them has to import another to share
the name or the test.
"""

from __future__ import annotations

# Set on a row by ``comms_governance`` and read by the formatter. The stored ``binding`` column is
# not what the formatter trusts, so a row that reaches it by any other path renders as ordinary.
BINDING_MARK = "_binding"


def is_binding_row(row: dict) -> bool:
    """True only when the row's ``binding`` is ``1``: the value ``post_directive`` writes and the
    standing-orders query (``binding=1``) selects. ``0``, ``None``, a missing key, ``2`` and the
    string ``"1"`` are not binding, so a row is an order for every reader or for none.
    """
    return row.get("binding") == 1
