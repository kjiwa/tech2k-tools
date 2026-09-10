# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from pathlib import Path

block_cipher = None

SPEC_DIR = Path(SPECPATH).resolve() if "SPECPATH" in globals() else Path("packaging").resolve()
REPO_ROOT = SPEC_DIR.parent
SRC_INVENTORY = REPO_ROOT / "inventory_updater" / "src"
SRC_MARCONE = REPO_ROOT / "marcone" / "src"
PKG_DIR = REPO_ROOT / "packaging"

is_darwin = sys.platform == "darwin"
is_windows = sys.platform == "win32"

datas = [
    (str(SRC_INVENTORY / "inventory_updater" / "assets"), "inventory_updater/assets"),
    (str(PKG_DIR / "icon.png"), "packaging"),
]
if (PKG_DIR / "icon.ico").exists():
    datas.append((str(PKG_DIR / "icon.ico"), "packaging"))
if (PKG_DIR / "icon.icns").exists():
    datas.append((str(PKG_DIR / "icon.icns"), "packaging"))

icon_file = None
if is_darwin and (PKG_DIR / "icon.icns").exists():
    icon_file = str(PKG_DIR / "icon.icns")
elif is_windows and (PKG_DIR / "icon.ico").exists():
    icon_file = str(PKG_DIR / "icon.ico")

version_file = str(PKG_DIR / "version_info.txt") if is_windows else None

a = Analysis(
    [str(SRC_INVENTORY / "inventory_updater" / "gui.py")],
    pathex=[str(SRC_INVENTORY), str(SRC_MARCONE)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "openpyxl",
        "openpyxl.cell._writer",
        "marcone",
        "marcone.client",
        "marcone.exceptions",
        "marcone.models",
        "inventory_updater",
        "inventory_updater.cache",
        "inventory_updater.credentials",
        "inventory_updater.styles",
        "inventory_updater.updater",
        "inventory_updater.gui",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "numpy",
        "pandas",
        "tkinter",
        "unittest",
        "pytest",
        "ruff",
        "IPython",
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
    name="Tech2000-InventoryUpdater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
    version=version_file,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Tech2000-InventoryUpdater",
)

if is_darwin:
    app = BUNDLE(
        coll,
        name="Tech2000-InventoryUpdater.app",
        icon=icon_file,
        bundle_identifier="com.tech2k.inventoryupdater",
        info_plist={
            "CFBundleName": "Tech 2000 Inventory Price Updater",
            "CFBundleDisplayName": "Tech 2000 Inventory Price Updater",
            "CFBundleIdentifier": "com.tech2k.inventoryupdater",
            "CFBundleVersion": "0.1.0",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundlePackageType": "APPL",
            "CFBundleSignature": "????",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "12.0",
            "LSApplicationCategoryType": "public.app-category.business",
        },
    )
