# -*- mode: python ; coding: utf-8 -*-
# charge_history_ui.spec
# 使用方式：python -m PyInstaller charge_history/charge_history_ui.spec

from pathlib import Path

block_cipher = None

SPEC_DIR = Path(SPECPATH)

a = Analysis(
    [str(SPEC_DIR / "charge_history_ui.py")],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=[
        (str(SPEC_DIR / "charge.png"), "."),
    ],
    hiddenimports=[
        "PyQt5.QtCore",
        "PyQt5.QtGui",
        "PyQt5.QtWidgets",
        "PyQt5.sip",
        "requests",
        "urllib3",
        "urllib3.util",
        "urllib3.util.retry",
        "urllib3.util.timeout",
        "urllib3.contrib",
        "charset_normalizer",
        "certifi",
        "idna",
        "email",
        "email.message",
        "email.parser",
        "email.errors",
        "email.utils",
        "http",
        "http.client",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "numpy", "pandas", "scipy", "matplotlib", "PIL", "Pillow",
        "cv2", "sklearn", "tensorflow", "torch", "torchvision",
        "IPython", "jupyter", "notebook",
        "PyQt5.QtBluetooth", "PyQt5.QtDBus", "PyQt5.QtDesigner",
        "PyQt5.QtHelp", "PyQt5.QtLocation", "PyQt5.QtMultimedia",
        "PyQt5.QtMultimediaWidgets", "PyQt5.QtNetwork",
        "PyQt5.QtNfc", "PyQt5.QtOpenGL", "PyQt5.QtPositioning",
        "PyQt5.QtPrintSupport", "PyQt5.QtQml", "PyQt5.QtQuick",
        "PyQt5.QtQuickWidgets", "PyQt5.QtRemoteObjects",
        "PyQt5.QtSensors", "PyQt5.QtSerialPort", "PyQt5.QtSql",
        "PyQt5.QtSvg", "PyQt5.QtTest", "PyQt5.QtWebChannel",
        "PyQt5.QtWebEngine", "PyQt5.QtWebEngineCore",
        "PyQt5.QtWebEngineWidgets", "PyQt5.QtWebSockets",
        "PyQt5.QtXml", "PyQt5.QtXmlPatterns",
        "tkinter", "unittest", "xmlrpc",
        "ftplib", "imaplib", "poplib", "smtplib", "telnetlib",
        "http.server",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="charge_history_ui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        "qwindows.dll",
        "qwindowsvistastyle.dll",
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SPEC_DIR / "charge.png"),
)
