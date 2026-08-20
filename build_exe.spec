# -*- mode: python ; coding: utf-8 -*-
"""Offline onedir pack: Python runtime + winsdk + pytesseract. Tesseract binaries are copied by the build script."""

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

datas = [("config.yaml", ".")]
binaries = []
hiddenimports = [
    "cv2",
    "numpy",
    "PIL",
    "PIL.Image",
    "yaml",
    "pyautogui",
    "pytesseract",
    "mouseinfo",
    "pyscreeze",
    "pymsgbox",
    "pytweening",
    "src.app",
    "src.calibrator",
    "src.capture",
    "src.conditions",
    "src.config",
    "src.control",
    "src.events",
    "src.monitor",
    "src.nan_counter",
    "src.ocr_engine",
    "src.paths",
    "src.recovery",
    "winsdk",
    "winsdk.windows.media.ocr",
    "winsdk.windows.graphics.imaging",
    "winsdk.windows.storage.streams",
    "winsdk.windows.globalization",
]

winsdk_datas, winsdk_binaries, winsdk_hidden = collect_all("winsdk")
datas += winsdk_datas
binaries += winsdk_binaries
hiddenimports += winsdk_hidden
hiddenimports += collect_submodules("src")

a = Analysis(
    ["launch.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "easyocr",
        "torch",
        "torchvision",
        "paddleocr",
        "paddle",
        "ultralytics",
        "pandas",
        "matplotlib",
        "scipy",
        "numba",
        "llvmlite",
        "pyarrow",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "tkinter.test",
        "IPython",
        "notebook",
        "jupyter",
        "pytest",
        "streamlit",
        "tensorflow",
        "sklearn",
        "skimage",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SideBendingRestartAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    uac_admin=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SideBendingRestartAgent",
)
