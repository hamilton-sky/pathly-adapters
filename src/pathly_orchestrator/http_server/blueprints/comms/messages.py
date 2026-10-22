"""Comms messages blueprint — re-exports bp after loading route sub-modules.

Routes split by concern:
  messages_read.py   — GET /comms, POST /comms/search (read only)
  messages_write.py  — POST /comms/post (the heavy write handler)
  messages_crud.py   — POST /comms/acknowledge, answer, edit, delete, supersede, restore and
                       GET /comms/trash
"""

from ._messages_bp import bp

# Import sub-modules to register their routes against bp.
from . import messages_crud, messages_read, messages_write

ROUTE_MODULES = (messages_read, messages_write, messages_crud)

__all__ = ["bp", "ROUTE_MODULES"]
