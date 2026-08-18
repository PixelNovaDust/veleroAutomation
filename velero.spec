# PyInstaller spec for the Velero automation executable.
#
# Build with:
#     pyinstaller velero.spec
#
# The result is dist/VeleroAutomation.exe. config, logs, data and
# backups are read next to the executable at run time, so the
# folder that gets copied to OneDrive looks like this:
#
#     VeleroAutomation.exe
#     config/config.json
#     logs/
#     data/
#     backups/
#
# A copy of config.json is bundled inside the executable as a
# fallback, used only when config/config.json is missing.

import os


block_cipher = None

project_root = os.path.abspath(SPECPATH)


analysis = Analysis(
    ["run.py"],
    pathex=[project_root],
    binaries=[],
    datas=[
        (os.path.join(project_root, "config", "config.json"), "config")
    ],
    hiddenimports=[
        "win32com.client",
        "pythoncom",
        "pywintypes"
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "pydoc_data"
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    analysis.pure,
    analysis.zipped_data,
    cipher=block_cipher
)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    [],
    name="VeleroAutomation",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None
)
