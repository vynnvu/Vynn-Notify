# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('characters', 'characters'), ('pet/surface_scan.ps1', 'pet'), ('pet/check.svg', 'pet')],
    hiddenimports=['characters.chibi_boy.renderer'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
# Ship authored resources only, never local bytecode from removed models.
a.datas = [entry for entry in a.datas if '__pycache__' not in entry[0].replace('\\', '/').split('/')]
# This app paints raster/QPainter widgets; it does not use QML, PDF,
# virtual keyboards or the software OpenGL fallback shipped by Qt.
unused_qt = {'opengl32sw.dll', 'Qt6Quick.dll', 'Qt6Pdf.dll', 'Qt6Qml.dll',
             'Qt6QmlMeta.dll', 'Qt6QmlModels.dll', 'Qt6QmlWorkerScript.dll',
             'Qt6VirtualKeyboard.dll'}
kept_plugins = {'qwindows.dll', 'qoffscreen.dll', 'qmodernwindowsstyle.dll',
                'qsvg.dll', 'qsvgicon.dll', 'qico.dll', 'qgif.dll', 'qjpeg.dll',
                'qschannelbackend.dll', 'qnetworklistmanager.dll'}
def needed_binary(entry):
    path = entry[0].replace('\\', '/')
    name = path.rsplit('/', 1)[-1]
    return name not in unused_qt and ('PySide6/plugins/' not in path or name in kept_plugins)
a.binaries = [entry for entry in a.binaries if needed_binary(entry)]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Vynn_Notify',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/chibi.ico'],
)
