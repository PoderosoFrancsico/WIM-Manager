"""Solicita elevación UAC y abre la aplicación con el mismo Python."""
import ctypes
from pathlib import Path
import subprocess
import sys

app = Path(__file__).resolve().with_name('main.py')
if ctypes.windll.shell32.IsUserAnAdmin():
    sys.exit(subprocess.call([sys.executable, str(app)]))
result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable,
                                          subprocess.list2cmdline([str(app)]),
                                          str(app.parent), 1)
if result <= 32:
    print('No se abrió WIM Manager. La elevación fue cancelada o Windows la rechazó.')
    sys.exit(1)
