# -*- mode: python ; coding: utf-8 -*-
# charger_monitor.spec
# 使用方式：pyinstaller charger_monitor.spec
#
# station.json 不打包 —— 请将其放在可执行文件的同目录下让用户自行配置

block_cipher = None
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent

a = Analysis(
    [str(SPEC_DIR / 'main.py')],
    pathex=[str(SPEC_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt5 运行时动态加载的模块，需手动声明
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        # requests 依赖链
        'requests',
        'urllib3',
        'urllib3.util',
        'urllib3.util.retry',
        'urllib3.util.timeout',
        'urllib3.contrib',
        'charset_normalizer',
        'certifi',
        'idna',
        # 标准库（urllib3 间接依赖）
        'email',
        'email.message',
        'email.parser',
        'email.errors',
        'email.utils',
        'http',
        'http.client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除所有不需要的大型库，减小体积
        'numpy', 'pandas', 'scipy', 'matplotlib', 'PIL', 'Pillow',
        'cv2', 'sklearn', 'tensorflow', 'torch', 'torchvision',
        'IPython', 'jupyter', 'notebook',
        'PyQt5.QtBluetooth', 'PyQt5.QtDBus', 'PyQt5.QtDesigner',
        'PyQt5.QtHelp', 'PyQt5.QtLocation', 'PyQt5.QtMultimedia',
        'PyQt5.QtMultimediaWidgets', 'PyQt5.QtNetwork',
        'PyQt5.QtNfc', 'PyQt5.QtOpenGL', 'PyQt5.QtPositioning',
        'PyQt5.QtPrintSupport', 'PyQt5.QtQml', 'PyQt5.QtQuick',
        'PyQt5.QtQuickWidgets', 'PyQt5.QtRemoteObjects',
        'PyQt5.QtSensors', 'PyQt5.QtSerialPort', 'PyQt5.QtSql',
        'PyQt5.QtSvg', 'PyQt5.QtTest', 'PyQt5.QtWebChannel',
        'PyQt5.QtWebEngine', 'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngineWidgets', 'PyQt5.QtWebSockets',
        'PyQt5.QtXml', 'PyQt5.QtXmlPatterns',
        'sqlite3', 'tkinter', 'unittest', 'xmlrpc',
        'ftplib', 'imaplib', 'poplib', 'smtplib', 'telnetlib',
        'http.server',
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
    name='充电桩监控',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        'qwindows.dll',
        'qwindowsvistastyle.dll',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(SPEC_DIR / "icon.png"),
)
