# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# 1. Collect all the heavy libraries
tmp_binaries, tmp_datas, tmp_hiddenimports = collect_all('PyQt6')
web_bin, web_dat, web_hidden = collect_all('PyQt6.QtWebEngineCore')
wid_bin, wid_dat, wid_hidden = collect_all('PyQt6.QtWebEngineWidgets')

a = Analysis(
    ['bookah.py'],
    pathex=[],
    binaries=tmp_binaries + web_bin,
    datas=[
        ('all_skills.json', '.'), 
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
    ] + tmp_datas + web_dat,
    hiddenimports=[
        'PyQt6.QtWebEngineWidgets', 
        'PyQt6.QtWebEngineCore', 
        'sklearn.utils._typedefs',
        'scipy.special.cython_special'
    ] + tmp_hiddenimports + web_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    
    excludes=[
        'tkinter', 'matplotlib', 'notebook', 'jedi', 
        'nvidia', 'PIL', 'pytest', 'pip'
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