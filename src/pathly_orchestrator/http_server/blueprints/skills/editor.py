"""Skills editor blueprint — re-exports bp after loading route sub-modules.

Routes split by concern:
  editor_render.py  — catalog, parse, preview, compose, summary-format
  editor_io.py      — save, export
"""

from ._editor_bp import bp  # noqa: F401

# Import sub-modules to register their routes against bp.
from . import editor_render as _er  # noqa: F401
from . import editor_io as _ei  # noqa: F401
