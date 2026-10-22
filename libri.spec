# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files

a = Analysis(
    ['main.py'],  # Il tuo script principale
    pathex=[],
    binaries=[],
    datas=[
        # (Sorgente, Destinazione)
        # Includi la cartella 'app' e 'motore' (necessarie per gli import)
        ('app', 'app'),
        ('motore', 'motore'),
        # Includi i file di CustomTkinter dal Python usato per la build.
        *collect_data_files('customtkinter'),
        # Se hai un'icona, decommenta e modifica la riga sotto
        # ('icona.ico', '.'),
    ],
    hiddenimports=[
        # I paragrafi generati importano questi moduli dinamicamente.
        'motore.componenti',
        'motore.stili',
        # Moduli che PyInstaller potrebbe non trovare da solo
        'PIL._imaging',
        'reportlab.graphics.barcode',
        'matplotlib.backends.backend_tkagg',
        'pymupdf',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Dipendenze opzionali per audio/AI presenti nell'ambiente di build,
        # non utilizzate da LIBRI e molto pesanti da distribuire.
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