# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('latest_version.json', '.'),
        ('app', 'app'),
        ('motore', 'motore'),
        ('assets', 'assets'),
        *collect_data_files('customtkinter'),
    ],
    hiddenimports=[
        *collect_submodules('app'),
        *collect_submodules('motore'),
        'motore.componenti',
        'motore.stili',
        'PIL._imaging',
        'reportlab.graphics.barcode',
        'matplotlib.backends.backend_tkagg',
        'pymupdf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'torch',
        'torchaudio',
        'transformers',
        'TTS',
        'trainer',
        'scipy',
        'sklearn',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LIBRI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/libri.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LIBRI',
)
