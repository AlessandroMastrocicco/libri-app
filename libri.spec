# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['main.py'],  # Il tuo script principale
    pathex=[],
    binaries=[],
    datas=[
        # (Sorgente, Destinazione)
        # Includi la cartella 'app' e 'motore' (necessarie per gli import)
        ('app', 'app'),
        ('motore', 'motore'),
        # Includi i file di CustomTkinter (obbligatorio)
        ('.venv/Lib/site-packages/customtkinter', 'customtkinter'),
        # Se hai un'icona, decommenta e modifica la riga sotto
        # ('icona.ico', '.'),
    ],
    hiddenimports=[
        # Moduli che PyInstaller potrebbe non trovare da solo
        'PIL._imaging',
        'reportlab.graphics.barcode',
        'matplotlib.backends.backend_tkagg',
        'pymupdf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LIBRI',  # Nome del tuo .exe
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # True per mostrare la console (utile per il debug)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Se hai un'icona, decommenta e modifica la riga sotto
    # icon='icona.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LIBRI',  # Nome della cartella di output
)