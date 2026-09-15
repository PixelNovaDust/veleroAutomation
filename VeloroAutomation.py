"""
Entry point for source runs and the PyInstaller executable.

Run from source:
    python VeloroAutomation.py

Build executable:
    pyinstaller velero.spec

When frozen, config, logs, data, backups and the ledger are read
and written next to VeloroAutomation.exe so edited config.json
and runtime data survive rebuilds.
"""

import os
import sys


def _bootstrap_path():

    entry_directory = os.path.dirname(
        os.path.abspath(__file__)
    )

    if entry_directory not in sys.path:
        sys.path.insert(0, entry_directory)


if __name__ == "__main__":

    _bootstrap_path()

    from app.main import main

    sys.exit(main())
