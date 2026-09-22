# PyInstaller spec for Vision Agent.
#
# Run this ON WINDOWS (PyInstaller does not cross-build): 
#     pyinstaller vision_agent.spec
#
# Produces dist/VisionAgent/VisionAgent.exe (onedir build -- easier to
# debug and to drop vision_agent_config.ini / swatches / fabric_part_images
# next to it, same layout the original VisionAgent.exe package used).

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PIL',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='VisionAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX apagado a proposito: la compresion UPX es uno de los patrones
    # que mas dispara heuristicas de antivirus (el malware real tambien
    # la usa para evadir analisis estatico). Un binario sin comprimir
    # tarda un poco mas en generarse pero se marca menos como sospechoso.
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='vision_agent.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='VisionAgent',
)
