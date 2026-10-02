# Build with: .venv\Scripts\python.exe -m PyInstaller BriefingMeteorologico.spec
from PyInstaller.utils.hooks import collect_all, collect_data_files

ctk_data, ctk_binaries, ctk_hidden = collect_all("customtkinter")
datas = ctk_data + collect_data_files("certifi") + collect_data_files("pyproj")

a = Analysis(
    ["main.py"],
    pathex=[SPECPATH],
    binaries=ctk_binaries,
    datas=datas,
    hiddenimports=ctk_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="BriefingMeteorologico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    uac_admin=False,
)
