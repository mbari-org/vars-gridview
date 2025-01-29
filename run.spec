# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['src/vars_gridview/scripts/run.py'],
    pathex=[],
    binaries=[],
    datas=[('src/vars_gridview/assets', 'assets')],
    hiddenimports=[],
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
    name='run',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity='Developer ID Application: Monterey Bay Aquarium Research Institute (9TN7A342V4)',
    entitlements_file=None,
    icon=['src/vars_gridview/assets/icons/VARSGridView.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='run',
)
app = BUNDLE(
    coll,
    name='VARS GridView.app',
    icon='src/vars_gridview/assets/icons/VARSGridView.icns',
    bundle_identifier='org.mbari.vars.gridview',
)
