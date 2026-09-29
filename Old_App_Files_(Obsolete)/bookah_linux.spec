# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

# 1. Collect PyQt6
tmp_binaries, tmp_datas, tmp_hiddenimports = collect_all('PyQt6')

# Filter out heavy WebEngine and other unused Qt modules
tmp_binaries = [x for x in tmp_binaries if not any(mod in x[0] for mod in ['WebEngine', 'Qml', 'Quick', 'Pdf', 'Multimedia', 'Bluetooth', 'Nfc', 'Sensors'])]

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
        ('data/description_embeddings.npz', '.'),
        ('onnx_model', 'onnx_model'),
        ('icons', 'icons'),
        ('version.json', '.'),
        ('history_note.md', '.'),
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

# Filter out system libraries that should be provided by the Flatpak runtime
# This prevents GLIBC version mismatch errors (e.g., libsystemd requiring newer GLIBC)
excluded_binaries = [
    'libsystemd.so.0',
    'libdbus-1.so.3',
    'libgpg-error.so.0',
    'libgcrypt.so.20',
    'liblzma.so.5',
    'libzstd.so.1',
    'liblz4.so.1',
    'libcap.so.2',
    'libgcc_s.so.1',
    'libstdc++.so.6',
    'libz.so.1'
]
a.binaries = [x for x in a.binaries if x[0] not in excluded_binaries]

# Strip any remaining bloat from the analysis object directly
bloat_keywords = ['torch', 'webengine', 'transformers', 'sentence_transformers', 'pyvis', 'networkx', 'qtqml', 'qtquick', 'qtpdf']
a.binaries = [x for x in a.binaries if not any(keyword in x[0].lower() for keyword in bloat_keywords)]
a.datas = [x for x in a.datas if not any(keyword in x[0].lower() for keyword in bloat_keywords)]

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