# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

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

def read_version():
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["project"]["version"]


def windows_version_info(version):
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo,
        StringFileInfo,
        StringStruct,
        StringTable,
        VarFileInfo,
        VarStruct,
        VSVersionInfo,
    )

    parts = tuple(int(p) for p in version.split(".")) + (0,)
    dotted = ".".join(str(p) for p in parts)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=parts,
            prodvers=parts,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "Tech 2000"),
                            StringStruct("FileDescription", "Tech 2000 Inventory Price Updater"),
                            StringStruct("FileVersion", dotted),
                            StringStruct("InternalName", "inventory_updater"),
                            StringStruct("LegalCopyright", "Copyright (c) 2026 Tech 2000"),
                            StringStruct("OriginalFilename", "Tech2000-InventoryUpdater.exe"),
                            StringStruct("ProductName", "Tech 2000 Inventory Price Updater"),
                            StringStruct("ProductVersion", dotted),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )


version_file = windows_version_info(read_version()) if is_windows else None

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
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

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
            "CFBundleVersion": read_version(),
            "CFBundleShortVersionString": read_version(),
            "CFBundlePackageType": "APPL",
            "CFBundleSignature": "????",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            "LSMinimumSystemVersion": "12.0",
            "LSApplicationCategoryType": "public.app-category.business",
        },
    )
