"""Comms messages blueprint — re-exports bp after loading route sub-modules.

Routes split by concern:
  messages_write.py  — POST /comms/post (the heavy write handler)
  messages_crud.py   — GET /comms, search, ack, answer, edit, delete, trash, restore
"""

from ._messages_bp import bp  # noqa: F401

# Import sub-modules to register their routes against bp.
from . import messages_crud as _mc  # noqa: F401
from . import messages_write as _mw  # noqa: F401
