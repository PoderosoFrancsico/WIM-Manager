"""WIM Manager: GUI de Windows para DISM, sin paquetes externos."""
import ctypes
import datetime
import locale
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def normalize(value):
    value = value.strip().strip('"')
    if not value:
        raise ValueError('Seleccioná una ruta.')
    return os.path.normpath(os.path.abspath(os.path.expandvars(value)))


def parse_images(output):
    images = []
    for line in output.splitlines():
        match = re.match(r'^\s*Index\s*:\s*(\d+)\s*$', line, re.I)
        if match:
            images.append({'index': int(match[1]), 'name': '', 'size': ''})
        elif images:
            field = re.match(r'^\s*(Name|Size)\s*:\s*(.*)$', line, re.I)
            if field:
                images[-1][field[1].lower()] = field[2].strip()
    return images


def mount_folder(image, supplied, base):
    if supplied.strip():
        target = Path(normalize(supplied))
        target.mkdir(parents=True, exist_ok=True)
        if any(target.iterdir()):
            raise ValueError('La carpeta de montaje debe estar vacía.')
        return str(target)
    parent = Path(normalize(base))
    parent.mkdir(parents=True, exist_ok=True)
    stem = Path(image).stem
    number = 0
    while True:
        target = parent / (stem if number == 0 else f'{stem} ({number})')
        try:
            target.mkdir()
            return str(target)
        except FileExistsError:
            number += 1


def is_admin():
    return os.name == 'nt' and bool(ctypes.windll.shell32.IsUserAnAdmin())


def dism_executable():
    windows = Path(os.environ.get('SystemRoot', r'C:\Windows'))
    native = windows / 'Sysnative' / 'dism.exe'
    return str(native if native.exists() else windows / 'System32' / 'dism.exe')


ERRORS = {
    2: 'No se encontró un archivo o una ruta. Revisá el registro.',
    5: 'Acceso denegado. Ejecutá como administrador y revisá los permisos.',
    50: 'La operación no está admitida por esta versión de DISM o esta imagen.',
    87: 'DISM rechazó un parámetro. Revisá el comando, la versión de DISM y la compatibilidad de la imagen.',
    112: 'No hay espacio suficiente en el disco.',
    740: 'La operación requiere permisos de administrador.',
    1392: 'DISM detectó un archivo o directorio dañado.',
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('WIM Manager • DISM')
        self.geometry('1080x790')
        self.minsize(900, 690)
        self.events = queue.Queue()
        self.busy = False
        self.buttons = []
        self.analyzed_path = None
        self.image_indices = set()
        self.wim = tk.StringVar()
        self.mount = tk.StringVar()
        self.base = tk.StringVar(value=r'C:\WIM_Mount')
        self.dism = tk.StringVar(value=dism_executable())
        self.legacy = tk.BooleanVar(value=False)
        self.readonly = tk.BooleanVar(value=True)
        self.integrity = tk.BooleanVar(value=True)
        self.index = tk.StringVar(value='1')
        self.status = tk.StringVar(value='Listo')
        self.percent = tk.DoubleVar()
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TButton', padding=7)
        style.configure('Title.TLabel', font=('Segoe UI', 19, 'bold'))
        self.build()
        self.after(80, self.poll)
        self.protocol('WM_DELETE_WINDOW', self.close)

    def button(self, parent, text, command):
        widget = ttk.Button(parent, text=text, command=lambda: self.safe(command))
        self.buttons.append(widget)
        return widget

    def safe(self, command):
        if self.busy:
            return
        try:
            command()
        except (OSError, ValueError) as exc:
            messagebox.showerror('Revisar datos', str(exc), parent=self)

    def path_row(self, parent, label, variable, mode='directory', save=False):
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=4)
        ttk.Label(row, text=label, width=22).pack(side='left')
        ttk.Entry(row, textvariable=variable).pack(side='left', fill='x', expand=True)
        def choose():
            if mode == 'directory':
                value = filedialog.askdirectory(parent=self)
            elif save:
                value = filedialog.asksaveasfilename(parent=self, defaultextension='.wim', filetypes=[('Imagen WIM', '*.wim')])
            else:
                value = filedialog.askopenfilename(parent=self, filetypes=[('Archivos', mode), ('Todos', '*.*')])
            if value:
                variable.set(os.path.normpath(value))
                if variable is self.wim:
                    self.analyze()
        self.button(row, 'Elegir…', choose).pack(side='left', padx=(8, 0))

    def build(self):
        main = ttk.Frame(self, padding=16)
        main.pack(fill='both', expand=True)
        top = ttk.Frame(main)
        top.pack(fill='x')
        ttk.Label(top, text='WIM Manager', style='Title.TLabel').pack(side='left')
        ttk.Label(top, text='Administrador' if is_admin() else 'Sin elevación • operaciones requieren administrador').pack(side='right')
        self.path_row(main, 'Archivo WIM', self.wim, '*.wim')
        controls = ttk.Frame(main)
        controls.pack(fill='x', pady=5)
        self.button(controls, 'Analizar índices', self.analyze).pack(side='left')
        ttk.Label(controls, text='Índice:').pack(side='left', padx=(16, 5))
        ttk.Entry(controls, textvariable=self.index, width=6).pack(side='left')
        self.button(controls, 'Ver imágenes montadas', lambda: self.run(['/Get-MountedWimInfo'])).pack(side='right')
        self.table = ttk.Treeview(main, columns=('index', 'name', 'size'), show='headings', height=4)
        for key, name, width in [('index', 'Índice', 65), ('name', 'Nombre de la imagen', 540), ('size', 'Tamaño informado por DISM', 220)]:
            self.table.heading(key, text=name)
            self.table.column(key, width=width)
        self.table.pack(fill='x', pady=(3, 10))
        self.table.bind('<<TreeviewSelect>>', self.select_index)
        tabs = ttk.Notebook(main)
        tabs.pack(fill='x')
        mount_tab = ttk.Frame(tabs, padding=12)
        transfer = ttk.Frame(tabs, padding=12)
        drivers = ttk.Frame(tabs, padding=12)
        settings = ttk.Frame(tabs, padding=12)
        for frame, title in [(mount_tab, 'Montaje'), (transfer, 'Aplicar / Capturar / Exportar'), (drivers, 'Drivers'), (settings, 'Configuración')]:
            tabs.add(frame, text=title)
        self.path_row(mount_tab, 'Carpeta de montaje', self.mount)
        ttk.Label(mount_tab, text='Vacía: crea una carpeta con el nombre del WIM; si existe, agrega (1), (2)…').pack(anchor='w')
        options = ttk.Frame(mount_tab)
        options.pack(fill='x', pady=8)
        ttk.Checkbutton(options, text='Montar solo lectura', variable=self.readonly).pack(side='left')
        ttk.Checkbutton(options, text='Sintaxis antigua /Mount-Wim', variable=self.legacy).pack(side='left', padx=18)
        row = ttk.Frame(mount_tab)
        row.pack(fill='x')
        for text, action in [('Montar', self.mount_image), ('Abrir carpeta', self.open_mount), ('Desmontar y guardar', lambda: self.unmount(True)), ('Desmontar y descartar', lambda: self.unmount(False)), ('Remontar', self.remount)]:
            self.button(row, text, action).pack(side='left', padx=(0, 6))
        self.destination = tk.StringVar()
        self.output = tk.StringVar()
        self.name = tk.StringVar(value='Imagen Windows')
        self.compression = tk.StringVar(value='fast')
        self.path_row(transfer, 'Carpeta origen / destino', self.destination)
        self.path_row(transfer, 'Archivo WIM de salida', self.output, '*.wim', save=True)
        row = ttk.Frame(transfer)
        row.pack(fill='x', pady=5)
        ttk.Label(row, text='Nombre:').pack(side='left')
        ttk.Entry(row, textvariable=self.name, width=28).pack(side='left', padx=6)
        ttk.Label(row, text='Compresión:').pack(side='left', padx=(12, 6))
        ttk.Combobox(row, textvariable=self.compression, values=('fast', 'max', 'none'), state='readonly', width=8).pack(side='left')
        for text, action in [('Aplicar WIM', self.apply_image), ('Capturar carpeta', self.capture_image), ('Exportar índice', self.export_image)]:
            self.button(row, text, action).pack(side='left', padx=5)
        self.driver_path = tk.StringVar()
        self.path_row(drivers, 'Carpeta de drivers', self.driver_path)
        row = ttk.Frame(drivers)
        row.pack(fill='x', pady=6)
        self.button(row, 'Listar drivers del montaje', lambda: self.driver_operation('list')).pack(side='left')
        self.button(row, 'Agregar drivers (recursivo)', lambda: self.driver_operation('add')).pack(side='left', padx=8)
        self.button(row, 'Exportar drivers', lambda: self.driver_operation('export')).pack(side='left')
        ttk.Label(drivers, text='Agregar drivers requiere una imagen montada con escritura. Guarda al desmontar.').pack(anchor='w', pady=7)
        self.path_row(settings, 'Ejecutable DISM', self.dism, '*.exe')
        self.path_row(settings, 'Base de montaje', self.base)
        ttk.Checkbutton(settings, text='Comprobar integridad en montaje, captura y exportación', variable=self.integrity).pack(anchor='w')
        self.button(settings, 'Información de DISM', lambda: self.run(['/?'])).pack(anchor='w', pady=6)
        row = ttk.Frame(main)
        row.pack(fill='x', pady=(12, 5))
        ttk.Label(row, textvariable=self.status).pack(side='left')
        self.button(row, 'Guardar registro', self.save_log).pack(side='right')
        ttk.Progressbar(main, variable=self.percent, maximum=100).pack(fill='x', pady=(0, 6))
        self.log = tk.Text(main, height=12, bg='#17212b', fg='#dce7f3', insertbackground='white', font=('Consolas', 10), wrap='word', state='disabled')
        self.log.pack(fill='both', expand=True)
        self.append('Seleccioná un WIM para analizarlo. No se modifica ninguna imagen hasta ejecutar una operación.\n')

    def select_index(self, _event):
        selected = self.table.selection()
        if selected:
            self.index.set(str(self.table.item(selected[0], 'values')[0]))

    def image(self):
        path = normalize(self.wim.get())
        if not Path(path).is_file() or Path(path).suffix.lower() != '.wim':
            raise ValueError('Seleccioná un archivo .wim existente.')
        return path

    def selected_image(self):
        path = self.image()
        try:
            index = int(self.index.get())
        except ValueError:
            raise ValueError('El índice debe ser un número entero positivo.')
        if index < 1:
            raise ValueError('El índice debe ser positivo.')
        if self.analyzed_path != os.path.normcase(path):
            raise ValueError('Analizá este WIM antes de seleccionar una operación.')
        if index not in self.image_indices:
            raise ValueError('Ese índice no aparece entre los índices analizados.')
        return path, index

    def require_admin(self):
        if not is_admin():
            raise ValueError('Cerrá y abrí con Iniciar.cmd para ejecutar como administrador.')

    def mounted_path(self):
        path = normalize(self.mount.get())
        if not Path(path).is_dir():
            raise ValueError('La carpeta de montaje no existe.')
        return path

    def analyze(self):
        path = self.image()
        self.analyzed_path = None
        self.image_indices.clear()
        self.table.delete(*self.table.get_children())
        def done(output):
            images = parse_images(output)
            if not images:
                messagebox.showwarning('Sin índices', 'No se pudieron interpretar los índices. Revisá el registro completo.')
                return
            self.analyzed_path = os.path.normcase(path)
            self.image_indices = {image['index'] for image in images}
            for image in images:
                self.table.insert('', 'end', values=(image['index'], image['name'], image['size']))
            first = self.table.get_children()[0]
            self.table.selection_set(first)
            self.index.set(str(images[0]['index']))
        self.run(['/Get-WimInfo', f'/WimFile:{path}'], done)

    def mount_image(self):
        self.require_admin()
        image, index = self.selected_image()
        target = mount_folder(image, self.mount.get(), self.base.get())
        self.mount.set(target)
        args = ['/Mount-Wim' if self.legacy.get() else '/Mount-Image', f'/WimFile:{image}' if self.legacy.get() else f'/ImageFile:{image}', f'/Index:{index}', f'/MountDir:{target}']
        if self.readonly.get():
            args.append('/ReadOnly')
        if self.integrity.get():
            args.append('/CheckIntegrity')
        self.run(args)

    def unmount(self, commit):
        self.require_admin()
        target = self.mounted_path()
        text = 'guardar los cambios' if commit else 'DESCARTAR los cambios'
        if messagebox.askyesno('Desmontar imagen', f'¿Desmontar {target} y {text}?', parent=self):
            self.run(['/Unmount-Wim' if self.legacy.get() else '/Unmount-Image', f'/MountDir:{target}', '/Commit' if commit else '/Discard'])

    def remount(self):
        self.require_admin()
        self.run(['/Remount-Wim' if self.legacy.get() else '/Remount-Image', f'/MountDir:{self.mounted_path()}'])

    def open_mount(self):
        os.startfile(self.mounted_path())

    def fresh_output(self):
        output = normalize(self.output.get())
        if Path(output).suffix.lower() != '.wim':
            raise ValueError('La salida debe terminar en .wim.')
        if Path(output).exists():
            raise ValueError('Elegí un archivo de salida nuevo para preservar las imágenes existentes.')
        if not Path(output).parent.is_dir():
            raise ValueError('La carpeta de salida no existe.')
        return output

    def apply_image(self):
        self.require_admin()
        image, index = self.selected_image()
        target = normalize(self.destination.get())
        if not Path(target).is_dir() or any(Path(target).iterdir()):
            raise ValueError('Elegí una carpeta de destino existente y vacía.')
        if messagebox.askyesno('Aplicar imagen', f'¿Extraer el índice {index} en {target}?', parent=self):
            self.run(['/Apply-Image', f'/ImageFile:{image}', f'/Index:{index}', f'/ApplyDir:{target}', '/Verify'])

    def capture_image(self):
        self.require_admin()
        source = normalize(self.destination.get())
        output = self.fresh_output()
        if not Path(source).is_dir():
            raise ValueError('La carpeta de origen no existe.')
        try:
            inside = os.path.commonpath([source, output]) == source
        except ValueError:
            inside = False
        if inside:
            raise ValueError('Guardá el WIM fuera de la carpeta que vas a capturar.')
        if not self.name.get().strip():
            raise ValueError('Ingresá un nombre para la imagen.')
        args = ['/Capture-Image', f'/CaptureDir:{source}', f'/ImageFile:{output}', f'/Name:{self.name.get().strip()}', f'/Compress:{self.compression.get()}', '/Verify']
        if self.integrity.get():
            args.append('/CheckIntegrity')
        self.run(args)

    def export_image(self):
        self.require_admin()
        image, index = self.selected_image()
        args = ['/Export-Image', f'/SourceImageFile:{image}', f'/SourceIndex:{index}', f'/DestinationImageFile:{self.fresh_output()}', f'/Compress:{self.compression.get()}']
        if self.integrity.get():
            args.append('/CheckIntegrity')
        self.run(args)

    def driver_operation(self, operation):
        self.require_admin()
        args = [f'/Image:{self.mounted_path()}']
        if operation == 'list':
            args.extend(['/Get-Drivers', '/Format:Table'])
        else:
            folder = normalize(self.driver_path.get())
            if not Path(folder).is_dir():
                raise ValueError('Seleccioná una carpeta de drivers existente.')
            if operation == 'add':
                if not messagebox.askyesno('Agregar drivers', f'¿Agregar todos los drivers de {folder} al montaje?', parent=self):
                    return
                args.extend(['/Add-Driver', f'/Driver:{folder}', '/Recurse'])
            else:
                if any(Path(folder).iterdir()):
                    raise ValueError('Para exportar drivers elegí una carpeta vacía.')
                args.extend(['/Export-Driver', f'/Destination:{folder}'])
        self.run(args)

    def run(self, args, callback=None):
        if self.busy:
            return
        executable = normalize(self.dism.get())
        if not Path(executable).is_file():
            raise ValueError('No se encontró DISM. Seleccioná su ejecutable en Configuración.')
        command = [executable, '/English'] + args
        self.busy = True
        self.percent.set(0)
        self.status.set('DISM en ejecución…')
        for button in self.buttons:
            button.configure(state='disabled')
        self.append('\n' + datetime.datetime.now().strftime('%H:%M:%S') + ' > ' + subprocess.list2cmdline(command) + '\n')
        def worker():
            output = []
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
                encoding = 'cp' + str(ctypes.windll.kernel32.GetOEMCP()) if os.name == 'nt' else locale.getpreferredencoding(False)
                buffer = bytearray()
                while True:
                    chunk = process.stdout.read(1)
                    if not chunk:
                        break
                    if chunk in (b'\r', b'\n'):
                        if buffer:
                            line = buffer.decode(encoding, errors='replace') + '\n'
                            output.append(line)
                            self.events.put(('line', line))
                            buffer.clear()
                    else:
                        buffer.extend(chunk)
                if buffer:
                    line = buffer.decode(encoding, errors='replace') + '\n'
                    output.append(line)
                    self.events.put(('line', line))
                code = process.wait()
                process.stdout.close()
                self.events.put(('done', code, ''.join(output), callback))
            except Exception as exc:
                self.events.put(('failed', str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == 'line':
                    self.append(event[1])
                    progress = re.search(r'(\d+(?:[.,]\d+)?)\s*%', event[1])
                    if progress:
                        self.percent.set(float(progress[1].replace(',', '.')))
                else:
                    self.busy = False
                    for button in self.buttons:
                        button.configure(state='normal')
                    if event[0] == 'failed':
                        self.status.set('No se pudo ejecutar DISM')
                        self.append(event[1] + '\n')
                        messagebox.showerror('Error de ejecución', event[1], parent=self)
                    else:
                        code, output, callback = event[1:]
                        self.append(f'\nCódigo de salida: {code}\n')
                        if code in (0, 3010):
                            self.percent.set(100)
                            self.status.set('Completado' if code == 0 else 'Completado • requiere reinicio')
                            if callback:
                                callback(output)
                        else:
                            self.status.set(f'Error DISM {code}')
                            messagebox.showerror('DISM no completó la operación', ERRORS.get(code, 'Revisá la salida completa del registro y C:\\Windows\\Logs\\DISM\\dism.log.') + f'\n\nCódigo: {code}\nNo se reintentó automáticamente.', parent=self)
        except queue.Empty:
            pass
        self.after(80, self.poll)

    def append(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text)
        self.log.see('end')
        self.log.configure(state='disabled')

    def save_log(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension='.txt', initialfile='wim-manager-log.txt')
        if path:
            Path(path).write_text(self.log.get('1.0', 'end-1c'), encoding='utf-8')

    def close(self):
        if self.busy:
            messagebox.showinfo('Operación en curso', 'Esperá a que DISM termine antes de cerrar.', parent=self)
        else:
            self.destroy()


if __name__ == '__main__':
    if os.name != 'nt':
        raise SystemExit('WIM Manager requiere Windows y DISM.')
    App().mainloop()
