# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# 1. Collect PyQt6
tmp_binaries, tmp_datas, tmp_hiddenimports = collect_all('PyQt6')

a = Analysis(
    ['bookah.py'],
    pathex=[],
    binaries=tmp_binaries,
    datas=[
        ('all_skills.json', '.'),
        ('sharecodes.json', '.'),
        ('master.db', '.'),
        ('skills_aq.db', '.'),
        ('skill_vectors.model', '.'),
        ('description_embeddings.pt', '.'),
        ('synergy_map.html', '.'),
        ('icons', 'icons'),
        ('version.json', '.'),
        ('user_manual.txt', '.'),
        ('LICENSE', '.'),
        ('third_party_notices.txt', '.')
    ] + tmp_datas,
    hiddenimports=[
        'sklearn.utils._typedefs',
        'scipy.special.cython_special'
    ] + tmp_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],

    excludes=[
        'tkinter', 'matplotlib', 'notebook', 'jedi',
        'nvidia', 'PIL', 'pytest', 'pip',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtWebEngineQuick'
    ],
    # ---------------------------
    noarchive=False,
)
pyz = PYZ(a.pure)

# 2. CHANGE: Create a lightweight executable (only scripts)
exe = EXE(
    pyz,
    a.scripts,
    [], # No binaries here
    exclude_binaries=True, # IMPORTANT: This enables One-Directory mode
    name='Bookah_Linux',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# 3. NEW: Collect everything into a folder
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name='Bookah_Linux',
)