# WIMapp.exe

`Crear_EXE.cmd` crea un ejecutable único en `dist\WIMapp.exe`, usando un entorno de compilación separado `.build-env`. Necesita Python e Internet en la computadora donde se compila.

El ejecutable incluye Python y Tcl/Tk. En la computadora de destino no hace falta instalar Python; sí necesita Windows y su DISM. Al abrir solicita permisos de administrador mediante UAC.

La compilación utiliza PyInstaller con `--onefile --windowed --uac-admin`. El modo de archivo único extrae los componentes internos a una carpeta temporal al abrirse.

El archivo `WIMapp.zip` en la raíz del repositorio conserva la versión fuente anterior a agregar esta configuración de compilación.

Documentación: https://www.pyinstaller.org/en/stable/usage.html
