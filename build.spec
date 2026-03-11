# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path

project_dir = Path.cwd()
src_dir = project_dir / "src"

a = Analysis(
    [str(src_dir / 'main.py')],
    pathex=[str(project_dir), str(src_dir)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'src.utils',
        'src.io_ops', 
        'src.headers',
        'src.validate',
        'src.expand',
        'src.sorters',
        'src.export',
        'src.version',
        'pandas._libs.tslibs.base',
        'openpyxl.cell._writer',
        'xlsxwriter.workbook'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MythosCards-Exporter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI için False
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)