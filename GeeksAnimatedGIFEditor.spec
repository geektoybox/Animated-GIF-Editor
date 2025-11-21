# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'AGIFEdit/assets'), ('geeks_gif_editor_settings.json', 'AGIFEdit')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeeksAnimatedGIFEditor',
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
    icon=['assets/GeeksGIFEditorLogo.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeeksAnimatedGIFEditor',
)
app = BUNDLE(
    coll,
    name='GeeksAnimatedGIFEditor.app',
    icon='assets/GeeksGIFEditorLogo.icns',
    bundle_identifier=None,
)
