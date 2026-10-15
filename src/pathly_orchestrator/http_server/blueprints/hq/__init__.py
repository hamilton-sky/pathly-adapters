"""HQ blueprints — the fleet copilot API (hq-copilot, local-operator).

Aggregated for registration in http_server/app.py (mirrors
comms/__init__.py and control/__init__.py): context (GET /hq/context, the
packet for inspection), prompt (POST /hq/prompt, the model turn Studio
sends), actions (GET /hq/actions + PUT /hq/actions/available, the operator
catalog) and actions_run (POST /hq/actions/check|run|report — proposals to
confirm cards to execution).
"""

from .actions import bp as hq_actions_bp
from .actions_run import bp as hq_actions_run_bp
from .context import bp as hq_context_bp
from .prompt import bp as hq_prompt_bp

all_blueprints = [hq_context_bp, hq_prompt_bp, hq_actions_bp, hq_actions_run_bp]
