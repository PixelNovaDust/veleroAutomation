"""
Entry point for both source runs and the PyInstaller build.

Keeping it outside the app package means the frozen executable
imports the package exactly the way `python run.py` does.
"""

import os
import sys


if __name__ == "__main__":

    sys.path.insert(
        0,
        os.path.dirname(os.path.abspath(__file__))
    )

    from app.main import main

    sys.exit(main())
