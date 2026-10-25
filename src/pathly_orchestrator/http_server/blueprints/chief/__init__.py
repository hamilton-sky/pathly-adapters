"""Chief blueprints — the chief agent's session API (chief-agent).

Aggregated for registration in app.py (mirrors control/__init__.py): session (POST /chief/open,
POST /chief/close, GET /chief/session), presets (GET /chief/presets), human (POST /chief/human-messages).
"""

from .human import bp as chief_human_bp
from .presets import bp as chief_presets_bp
from .session import bp as chief_session_bp

all_blueprints = [chief_session_bp, chief_presets_bp, chief_human_bp]
