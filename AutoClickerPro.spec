# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('src/styles', 'src/styles')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
        'tcl',
        'unittest',
        'pytest',
        'pytestqt',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtNetwork',
        'PySide6.QtDesigner',
        'PySide6.QtHelp',
        'PySide6.QtTest',
        'PySide6.QtSpatialAudio',
        'PySide6.QtSensors',
        'PySide6.QtPositioning',
        'PySide6.QtLocation',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
    ],
    noarchive=False,
    optimize=1,
)

# Trim unused Qt binaries & translations to drastically reduce executable size (~40-50MB smaller)
_DROP_BINARIES = (
    'opengl32sw.dll',
    'qt6pdf.dll',
    'qt6qml.dll',
    'qt6qmlmeta.dll',
    'qt6qmlmodels.dll',
    'qt6qmlworkerscript.dll',
    'qt6quick.dll',
    'qt6network.dll',
    'qt6opengl.dll',
    'qt6virtualkeyboard.dll',
    'qdirect2d.dll',
    'qoffscreen.dll',
    'qminimal.dll',
    'qpdf.dll',
    'qwebp.dll',
    'qtiff.dll',
    'qicns.dll',
    'qtga.dll',
    'qwbmp.dll',
    'qtvirtualkeyboardplugin.dll',
    'qtuiotouchplugin.dll',
)
a.binaries = [
    b for b in a.binaries
    if not any(drop in b[0].lower() for drop in _DROP_BINARIES)
]
a.datas = [
    d for d in a.datas
    if not ('translations' in d[0].lower() and d[0].lower().endswith('.qm'))
]

pyz = PYZ(a.pure)

# 1. Onedir build: Instant startup (< 0.5s), no temporary extraction overhead
exe_dir = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AutoClickerPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe_dir,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AutoClickerPro',
)

# 2. Portable Onefile build: Optimized standalone executable without UPX
exe_single = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AutoClickerPro-Portable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
)
