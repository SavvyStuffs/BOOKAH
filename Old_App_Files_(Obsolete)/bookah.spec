# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['bookah.py'],
    pathex=[],
    binaries=[],
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
        ('THIRD_PARTY_NOTICES.txt', '.')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'notebook', 'jedi',
        'nvidia', 'PIL', 'pytest', 'pip',
        'PyQt6.QtWebEngineWidgets', 
        'PyQt6.QtWebEngineCore', 
        'PyQt6.QtWebEngineQuick',
        'PyQt6.QtQml',
        'PyQt6.QtQuick',
        'PyQt6.QtPdf',
        'PyQt6.QtMultimedia',
        'PyQt6.QtBluetooth',
        'PyQt6.QtNfc',
        'PyQt6.QtSensors'
    ],
    noarchive=False,
    optimize=0,
)

# Strip any remaining bloat from the analysis object directly
bloat_keywords = ['torch', 'webengine', 'transformers', 'sentence_transformers', 'pyvis', 'networkx', 'qtqml', 'qtquick', 'qtpdf']
a.binaries = [x for x in a.binaries if not any(keyword in x[0].lower() for keyword in bloat_keywords)]
a.datas = [x for x in a.datas if not any(keyword in x[0].lower() for keyword in bloat_keywords)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Bookah',
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
    icon=['icons\\bookah_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Bookah',
)
