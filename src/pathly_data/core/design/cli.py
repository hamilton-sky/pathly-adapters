"""Entry point for the pathly-design CLI command.

Adds the bundled scripts directory to sys.path so search.py can import
core.py and design_system.py as sibling modules, then runs search.py.
"""
import sys
import runpy
from pathlib import Path


def main() -> None:
    scripts_dir = Path(__file__).parent / "scripts"
    sys.path.insert(0, str(scripts_dir))
    sys.argv[0] = "pathly-design"
    runpy.run_path(str(scripts_dir / "search.py"), run_name="__main__")
