from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
datas = [(str(root / 'qq_live_digest' / 'board.html'), 'qq_live_digest')]
binaries = []
hiddenimports = []
for package in ('PIL', 'pypdfium2'):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=binaries, datas=datas, hiddenimports=hiddenimports, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='qq-live-digest-personal', console=True, strip=False, upx=False, icon=str(root / 'assets' / 'icon.ico'))
