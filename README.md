# WIM Manager

Aplicación de escritorio para Windows que simplifica las operaciones con imágenes WIM mediante DISM.

## Abrir

Para usar la versión lista para Windows, descargar [WIMapp.exe](https://github.com/PoderosoFrancsico/WIM-Manager/raw/refs/heads/main/dist/WIMapp.exe). No necesita instalar Python. El archivo [WIMapp.zip](https://github.com/PoderosoFrancsico/WIM-Manager/raw/refs/heads/main/WIMapp.zip) conserva una copia de la versión fuente original.

Para ejecutar el código fuente:

1. Instalar Python 3.10 o superior para Windows, con Tcl/Tk y el lanzador `py`.
2. Abrir `Iniciar.cmd` y aceptar la solicitud de administrador de Windows.
3. Elegir un `.wim`. La aplicación consulta DISM y muestra sus índices.
4. Seleccionar un índice y la operación deseada.

No requiere instalar paquetes con pip. También puede ejecutarse `py -3 main.py` desde una terminal elevada. Usa el DISM de Windows; en Configuración se puede elegir otro ejecutable instalado, por ejemplo el de un ADK compatible.

## Funciones

- Analizar índices y mostrar nombre y tamaño de cada imagen.
- Montar con lectura o escritura y sintaxis moderna o antigua.
- Crear carpetas de montaje automáticamente en `C:\WIM_Mount`. Si existe `Nombre`, crea `Nombre (1)`, `Nombre (2)`, etc. Una ruta manual se crea si falta y se exige que esté vacía.
- Desmontar guardando o descartando cambios, con confirmación, y remontar imágenes.
- Consultar las imágenes montadas por DISM y abrir la carpeta seleccionada.
- Aplicar un índice a una carpeta vacía, capturar una carpeta en un WIM nuevo y exportar un índice a un WIM nuevo.
- Listar, agregar recursivamente y exportar drivers de una imagen montada.
- Mostrar progreso, comando ejecutado y salida de DISM. Guardar el registro en un archivo de texto.

Para modificar archivos o agregar drivers, desmarcar **Montar solo lectura** antes de montar. Usar **Desmontar y guardar** para conservar los cambios. Las operaciones se ejecutan de a una, en un hilo de trabajo, y el programa espera a que DISM termine antes de permitir cerrar.

## Imágenes antiguas y Error 87

La opción **Sintaxis antigua /Mount-Wim** es manual. No se vuelve a intentar una operación de escritura automáticamente. Las rutas se normalizan a formato Windows y se pasan como argumentos separados, sin usar un shell. El comando mostrado se escapa con `subprocess.list2cmdline`.

El Error 87 puede tener varias causas: la aplicación no presupone que normalizar rutas lo resuelva. Revisar la salida, la versión de DISM y su compatibilidad con el WIM. Para WES7, conservar una copia del original antes de trabajar con escritura. El registro nativo de DISM está en `%SystemRoot%\Logs\DISM\dism.log`.

## Validación

Desde esta carpeta:

```bat
py -3 -m py_compile main.py launcher.py
py -3 -m unittest discover -s tests -v
```

Las pruebas cubren la interpretación de índices y la creación de carpetas, sin invocar DISM ni modificar imágenes. La comprobación de sintaxis y las cuatro pruebas pasaron. También se generó correctamente el ejecutable con PyInstaller. Falta comprobar la interfaz en Windows y las operaciones reales con una copia de un WIM.

## Ejecutable único

`dist/WIMapp.exe` incluye Python y Tcl/Tk; no requiere instalar Python en la computadora donde se usa. Requiere Windows con DISM y solicita permisos de administrador al abrirse.

Para regenerarlo, ejecutar `Crear_EXE.cmd`. La compilación requiere Python e Internet y usa un entorno separado `.build-env`. Ver `EJECUTABLE.md` para más detalles.

Referencia de comandos: [Microsoft Learn: DISM Image Management Command-Line Options](https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/dism-image-management-command-line-options-s14).
